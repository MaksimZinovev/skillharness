#!/usr/bin/env python3
"""
SessionStart hook - Verifies keyword-filters.conf covers all available skills.

RUNS: At session start (before first user prompt)
CHECKS: That keyword-filters.conf has entries for all discovered skills
OUTPUT: Warning if skills are missing from config

============================================================================
HOW TO TEST
============================================================================

HOOK_PATH=".claude/hooks/session-start-verify-skills.py"

1. Run directly - should output JSON with missing skills or suppressOutput:true
   Command: echo '{"cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: JSON output. Either:
   - {"continue":true,"suppressOutput":true} if all skills covered, OR
   - {"continue":true,"suppressOutput":false,"systemMessage":"...missing skills..."} if gaps found

2. Debug mode - should log to /tmp/hook-debug.log
   Command: SKILL_HOOK_DEBUG=1 echo '{"cwd":"/tmp"}' | python3 $HOOK_PATH && cat /tmp/hook-debug.log
   Expected: Debug log with lines like:
   - [PID] === DISCOVERING SKILLS ===
   - [PID] Discovered X skills, Y enabled
   - [PID] === PARSING CONFIG ===
   - [PID] Config has Z skill entries

3. When all skills covered - suppressOutput: true
   Setup: Ensure keyword-filters.conf has entries for all enabled skills
   Command: echo '{"cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: {"continue":true,"suppressOutput":true}

4. When skills missing - shows systemMessage with fix instructions
   Setup: Remove some entries from keyword-filters.conf temporarily
   Command: echo '{"cwd":"/tmp"}' | python3 $HOOK_PATH
   Expected: JSON with suppressOutput:false and systemMessage containing:
   - "SESSION START NOTICE"
   - "Missing skill entries"
   - Auto-generate command suggestion

5. Verify JSON output format
   Command: echo '{"cwd":"/tmp"}' | python3 $HOOK_PATH | python3 -m json.tool
   Expected: Valid JSON with keys: continue, suppressOutput, and optionally systemMessage

6. Test with specific project directory
   Command: echo '{"cwd":"/Users/maksim/repos/github-stars-manager"}' | python3 $HOOK_PATH
   Expected: Checks skills in both ~/.claude/skills/ and project .claude/skills/

TROUBLESHOOTING:
- If "WARNING: Only X skills found": Skills directories may be empty or missing
- If always showing missing: Check keyword-filters.conf format (skill-name:keyword1,keyword2)
- If debug log empty: Ensure SKILL_HOOK_DEBUG=1 is set

============================================================================
"""

import json
import os
import re
import sys
from pathlib import Path

# Import shared utilities from same directory
from hook_utils import debug_log, discover_skills, is_skill_enabled

# ============================================================================
# CONSTANTS
# ============================================================================

MIN_SKILLS_THRESHOLD = 10  # Warn if fewer skills discovered (something's wrong)

# ============================================================================
# CONFIG FILE PARSING
# ============================================================================

def parse_keyword_filters(config_path: str | Path) -> set[str]:
    """Extract skill names from keyword-filters.conf.

    Args:
        config_path: Path to keyword-filters.conf file

    Returns:
        Set of skill names found in config (before the colon)
    """
    config_file = Path(config_path)
    if not config_file.exists():
        debug_log(f"Config file not found: {config_path}")
        return set()

    skills_in_config = set()

    with open(config_file) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Extract skill name (before colon)
            if ":" in line:
                skill_name = line.split(":", 1)[0].strip()
                if skill_name:
                    skills_in_config.add(skill_name)

    debug_log(f"Config has {len(skills_in_config)} skill entries")
    return skills_in_config


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    # Get current working directory from stdin or environment
    input_data = {}
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        pass

    cwd = input_data.get("cwd", os.getcwd())
    hook_dir = Path(__file__).parent
    keyword_config = hook_dir / "keyword-filters.conf"

    debug_log("=== DISCOVERING SKILLS ===")

    # Discover all skills
    all_skills = discover_skills(cwd)

    # Filter to only enabled skills
    enabled_skill_names = set()
    for skill in all_skills:
        if is_skill_enabled(skill["skill_file"], skill["plugin_name"]):
            enabled_skill_names.add(skill["name"])

    debug_log(f"Discovered {len(all_skills)} skills, {len(enabled_skill_names)} enabled")

    # Sanity check
    if len(enabled_skill_names) < MIN_SKILLS_THRESHOLD:
        debug_log(f"WARNING: Only {len(enabled_skill_names)} skills found (threshold: {MIN_SKILLS_THRESHOLD})")

    debug_log("=== PARSING CONFIG ===")

    # Get skills from config
    configured_skills = parse_keyword_filters(keyword_config)

    debug_log("=== FINDING MISSING ===")

    # Find enabled skills not in config
    missing_skills = sorted(enabled_skill_names - configured_skills)
    missing_count = len(missing_skills)

    if missing_count > 0:
        missing_list = ", ".join(missing_skills)
        debug_log(f"Missing skills: {missing_list}")

        # Build the system message (actual newlines, JSON will encode them)
        missing_comma_separated = ",".join(missing_skills)
        system_message = (
            f"SESSION START NOTICE: keyword-filters.conf is incomplete\n"
            f"\n"
            f"Missing skill entries ({missing_count}):\n"
            f"{missing_list}\n"
            f"\n"
            f"To fix, add entries to .claude/hooks/keyword-filters.conf:\n"
            f"  skill-name:keyword1,keyword2,keyword3\n"
            f"\n"
            f"Or run this to auto-generate:\n"
            f"  echo '{missing_comma_separated}' | tr ',' '\\n' | "
            f"while read skill; do echo \"\\${{skill}}:TODO\"; done >> .claude/hooks/keyword-filters.conf"
        )

        # Output JSON format for proper display to user
        result = {
            "continue": True,
            "suppressOutput": False,
            "systemMessage": system_message
        }
        print(json.dumps(result))
    else:
        debug_log("All skills covered")
        # Silent success - output empty JSON
        print(json.dumps({"continue": True, "suppressOutput": True}))


if __name__ == "__main__":
    main()
