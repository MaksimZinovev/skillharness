#!/usr/bin/env python3
"""
Smart Forced-Eval Hook - Discovers skills from directories and filters by keyword

DISCOVERY: Reads SKILL.md from ~/.claude/skills/, .claude/skills/, plugins
FILTERING: Matches user prompt against skill name + description
OUTPUT: Only lists relevant skills (7-10 max, not all 100+)

============================================================================
HOW TO TEST
============================================================================

HOOK_PATH=".claude/hooks/skill-forced-eval-hook.py"

1. Playwright test debugging - should suggest playwright, systematic-debugging
   Command: echo '{"prompt":"help me debug a playwright test that is failing","cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: Output JSON with "playwright" in systemMessage (and possibly "testing", "debug")

2. Generic prompt (what time is it) - should give minimal instruction
   Command: echo '{"prompt":"what time is it","cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: Output JSON with suppressOutput:false but no specific skills listed

3. Debug mode - should create /tmp/hook-debug.log
   Command: SKILL_HOOK_DEBUG=1 echo '{"prompt":"test debugging mode","cwd":"/tmp"}' | python3 $HOOK_PATH && cat /tmp/hook-debug.log
   Expected: Debug log file created with [PID] prefixed log lines

4. CircleCI pipeline - should suggest circleci-cli (if configured in keyword-filters.conf)
   Command: echo '{"prompt":"my circleci pipeline is failing","cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: Output JSON with "circleci" or similar CI skill in systemMessage

5. Disabled skill (playwright-cli) - should NOT appear even if keyword matches
   Note: This requires a skill with disable-model-invocation: true in its SKILL.md
   Command: echo '{"prompt":"use playwright-cli to run tests","cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: "playwright-cli" should NOT appear in systemMessage (but "playwright" might)

6. Verify JSON output format
   Command: echo '{"prompt":"run tests","cwd":"/tmp"}' | python3 $HOOK_PATH | python3 -m json.tool
   Expected: Valid JSON with keys: continue, suppressOutput, systemMessage

7. Multiple matching skills
   Command: echo '{"prompt":"debug a failing test in my browser automation suite","cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: Multiple skills listed (testing, playwright, debug, etc.)

TROUBLESHOOTING:
- If no skills found: Check that ~/.claude/skills/ or .claude/skills/ has SKILL.md files
- If debug log empty: Ensure SKILL_HOOK_DEBUG=1 is set in environment
- If wrong skills: Check keyword-filters.conf for keyword overrides

============================================================================
"""

import json
import os
import re
import sys
from pathlib import Path
from textwrap import dedent

# Import from hook_utils.py in the same directory
from hook_utils import parse_input, discover_skills, is_skill_enabled, debug_log

# ============================================================================
# CONSTANTS
# ============================================================================

MIN_WORD_LENGTH = 5  # Min chars for desc matching
MIN_KEYWORD_LENGTH = 3  # Min chars for config keywords
MAX_SKILLS_OUTPUT = 10  # Pre-filter to max 10 relevant skills

# Stopwords to skip when matching description words
STOPWORDS = {
    "the", "about", "above", "after", "again", "against", "being", "below",
    "between", "both", "could", "did", "does", "doing", "during", "each",
    "few", "from", "further", "had", "have", "having", "here", "hers", "him",
    "his", "into", "just", "more", "most", "must", "need", "only", "other",
    "over", "same", "should", "some", "such", "than", "that", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "under",
    "until", "very", "want", "what", "when", "where", "which", "while", "will",
    "with", "would", "your", "use", "used", "using", "user", "users", "skill",
    "skills", "claude", "create", "creating", "created", "check", "checks",
    "checking", "include", "includes", "including", "general", "generally",
    "workflow", "workflows", "help", "provides", "when", "need"
}


# ============================================================================
# KEYWORD CONFIG
# ============================================================================

def load_keyword_filters(config_path: str, prompt_lower: str) -> set:
    """Load keyword overrides from keyword-filters.conf.

    Args:
        config_path: Path to keyword-filters.conf file
        prompt_lower: Lowercase user prompt for matching

    Returns:
        Set of skill names that matched via config keywords
    """
    matched = set()
    config_file = Path(config_path)

    if not config_file.exists():
        debug_log(f"Config file not found: {config_path}")
        return matched

    debug_log("=== CONFIG OVERRIDES ===")

    try:
        for line in config_file.read_text().splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse format: skill_name:keyword1,keyword2,keyword3
            if ':' not in line:
                continue

            name, keywords = line.split(':', 1)
            name = name.strip()
            keywords = keywords.strip()

            if not name or not keywords:
                continue

            for kw in keywords.split(','):
                kw = kw.strip().lower()
                if len(kw) < MIN_KEYWORD_LENGTH:
                    continue

                # Check if keyword is in prompt (word boundary)
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, prompt_lower):
                    matched.add(name)
                    debug_log(f"Match(config '{kw}'): {name}")
                    break

    except Exception as e:
        debug_log(f"Error reading config: {e}")

    return matched


# ============================================================================
# MATCHING
# ============================================================================

def match_skill(name: str, description: str, prompt_lower: str) -> bool:
    """Check if a skill matches the user prompt.

    Args:
        name: Skill name
        description: Skill description
        prompt_lower: Lowercase user prompt

    Returns:
        True if skill matches prompt
    """
    name_lower = name.lower()
    desc_lower = description.lower()

    # Match 1: Skill name in prompt (word boundary)
    pattern = r'\b' + re.escape(name_lower) + r'\b'
    if re.search(pattern, prompt_lower):
        debug_log(f"Match(name): {name}")
        return True

    # Match 2: Significant words from description in prompt
    for word in desc_lower.split():
        if len(word) < MIN_WORD_LENGTH:
            continue
        if word in STOPWORDS:
            continue

        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, prompt_lower):
            debug_log(f"Match(desc '{word}'): {name}")
            return True

    return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    # Parse input from stdin
    data = parse_input()
    prompt = data.get("prompt", "")
    cwd = data.get("cwd", os.getcwd())

    if not prompt:
        debug_log("No prompt, exiting")
        return

    prompt_lower = prompt.lower()
    debug_log(f"Prompt: {prompt_lower[:50]}...")

    # ============================================================================
    # /noskill BYPASS - Skip all skill evaluation for this prompt
    # ============================================================================
    NOSKILL_PATTERN = re.compile(r'\b/noskill\b', re.IGNORECASE)

    if NOSKILL_PATTERN.search(prompt):
        debug_log("Bypass requested via /noskill")

        # Read existing state to get prompt_count
        STATE_FILE = Path("/tmp/skill-session-state.json")
        existing_state = {}
        if STATE_FILE.exists():
            try:
                existing_state = json.loads(STATE_FILE.read_text())
            except:
                pass

        state = {
            "skills_suggested": [],
            "selected_skill": None,
            "ask_question_answered": False,
            "no_skill_needed": True,  # KEY: Set bypass flag
            "activated": [],
            "prompt_count": existing_state.get("prompt_count", 0) + 1
        }

        # Atomic write
        TEMP_FILE = Path("/tmp/skill-session-state.tmp")
        with open(TEMP_FILE, 'w') as f:
            f.write(json.dumps(state, indent=2))
            f.flush()
            os.fsync(f.fileno())
        TEMP_FILE.rename(STATE_FILE)

        debug_log(f"Bypass state set: prompt_count={state['prompt_count']}")

        # Output empty additionalContext (no skill guidance)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ""
            }
        }
        json.dump(output, sys.stdout)
        return

    # ============================================================================
    # NORMAL FLOW - Discover and filter skills
    # ============================================================================

    # Discover all skills
    debug_log("=== DISCOVERING ===")
    all_skills = discover_skills(cwd)
    debug_log(f"Total: {len(all_skills)} skills")

    # Filter enabled skills
    enabled_skills = []
    for skill in all_skills:
        if is_skill_enabled(skill['skill_file'], skill['plugin_name']):
            enabled_skills.append(skill)
        else:
            debug_log(f"SKIP [{skill['name']}]: disabled")

    debug_log(f"Enabled: {len(enabled_skills)} skills")

    # Match skills against prompt
    debug_log("=== FILTERING ===")
    matched = set()

    # Match from skill names and descriptions
    for skill in enabled_skills:
        if match_skill(skill['name'], skill['description'], prompt_lower):
            matched.add(skill['name'])

    # Load keyword config overrides - only add enabled skills
    hook_dir = Path(__file__).parent
    keyword_config = hook_dir / "keyword-filters.conf"
    config_matched = load_keyword_filters(str(keyword_config), prompt_lower)

    # Build lookup of enabled skills by name
    enabled_names = {s['name'] for s in enabled_skills}

    for skill_name in config_matched:
        if skill_name in enabled_names:
            matched.add(skill_name)
        else:
            debug_log(f"SKIP config match [{skill_name}]: not enabled")

    # Limit to MAX_SKILLS_OUTPUT
    matched_list = sorted(list(matched))[:MAX_SKILLS_OUTPUT]
    debug_log(f"Final: {', '.join(matched_list)}")

    # Build output JSON using shared checkpoint formatter
    if matched_list:
        from hook_utils import format_skill_checkpoints
        system_message = format_skill_checkpoints(matched_list)
    else:
        system_message = ""  # No skills matched, silent pass-through

    # Output JSON
    output = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": f"First pay attention to the guidance and follow instructions:\n{system_message}",
    }
}
 
    # Write skills_suggested to state for other hooks (ATOMIC WRITE)
    STATE_FILE = Path("/tmp/skill-session-state.json")
    TEMP_FILE = Path("/tmp/skill-session-state.tmp")
    state = {
        "skills_suggested": matched_list,
        "selected_skill": None,  # Will be set by after-ask-question.py
        "ask_question_answered": False,  # Will be set by after-ask-question.py
        "no_skill_needed": False,  # Will be set by after-ask-question.py
        "activated": [],  # Will be set by track-skill-activation.py
        "prompt_count": 1
    }
    # Atomic write: write to temp file, sync, then rename
    with open(TEMP_FILE, 'w') as f:
        f.write(json.dumps(state, indent=2))
        f.flush()
        os.fsync(f.fileno())
    TEMP_FILE.rename(STATE_FILE)

    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
