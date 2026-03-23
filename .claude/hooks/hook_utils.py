#!/usr/bin/env python3
"""
Shared utilities for Claude Code hook scripts.

Provides common functions for parsing input, discovering skills,
checking enabled status, and debugging.

============================================================================
HOW TO TEST
============================================================================

HOOK_PATH=".claude/hooks/hook_utils.py"

1. Run directly - should test functions and print results
   Command: python3 $HOOK_PATH
   Expected: Output like:
   - "Hook utils module - testing functions..."
   - "Found X skills:"
   - List of skill names with (local) or (plugin_name)
   - "[skill_name] enabled: True/False"

2. Test parse_input with valid JSON
   Command: echo '{"prompt":"test prompt","cwd":"/tmp"}' | python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import parse_input; print(parse_input())"
   Expected: {'prompt': 'test prompt', 'cwd': '/tmp'}

3. Test parse_input with empty input
   Command: echo '' | python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import parse_input; print(parse_input())"
   Expected: {'prompt': '', 'cwd': '<current_directory>'}

4. Test debug_log with SKILL_HOOK_DEBUG enabled
   Command: SKILL_HOOK_DEBUG=1 python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import debug_log; debug_log('test message')" && cat /tmp/hook-debug.log
   Expected: Log file contains line with "[PID] test message"

5. Test debug_log without debug flag (should not create log)
   Command: rm -f /tmp/hook-debug.log && python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import debug_log; debug_log('test message')" && ls /tmp/hook-debug.log 2>&1
   Expected: "No such file or directory" error (log not created)

6. Test discover_skills from project directory
   Command: python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import discover_skills; skills = discover_skills('/Users/maksim/repos/github-stars-manager'); print(f'Total: {len(skills)}'); print('Names:', [s[\"name\"] for s in skills[:5]])"
   Expected: Number of skills found and first 5 skill names

7. Test is_skill_enabled on a known skill
   Command: python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import discover_skills, is_skill_enabled; skills = discover_skills('/tmp'); print('All enabled:', all(is_skill_enabled(s[\"skill_file\"], s[\"plugin_name\"]) for s in skills))"
   Expected: True or False depending on disabled skills

8. Test parse_frontmatter on a real SKILL.md
   Command: python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); from hook_utils import discover_skills, parse_frontmatter; skills = discover_skills('/tmp'); print(parse_frontmatter(skills[0]['skill_file']) if skills else 'No skills')"
   Expected: Dict with name, description, user-invocable, etc.

TROUBLESHOOTING:
- "No skills found": Ensure ~/.claude/skills/ exists with SKILL.md subdirectories
- Import errors: Run from project root or adjust sys.path
- Empty frontmatter: SKILL.md may lack YAML frontmatter (--- delimiters)

============================================================================
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_input() -> Dict[str, Any]:
    """Read JSON from stdin and return dict with prompt and cwd.

    Expected input format:
    {
        "prompt": "user message or hook context",
        "cwd": "/path/to/working/directory"
    }

    Returns:
        Dict with 'prompt' and 'cwd' keys. Empty dict if parsing fails.
    """
    try:
        data = json.loads(sys.stdin.read())
        return {
            "prompt": data.get("prompt", ""),
            "cwd": data.get("cwd", os.getcwd())
        }
    except json.JSONDecodeError:
        return {"prompt": "", "cwd": os.getcwd()}


def discover_skills(cwd: str) -> List[Dict[str, str]]:
    """Find all SKILL.md files from standard locations.

    Searches in order:
    1. ~/.claude/skills/ (personal skills)
    2. cwd/.claude/skills/ (project skills)
    3. ~/.claude/plugins/*/skills/ (plugin skills)

    Args:
        cwd: Current working directory path

    Returns:
        List of dicts with keys: name, description, skill_file, plugin_name
        plugin_name is None for personal/project skills.
    """
    skills = []
    home = Path.home()

    # Locations to search
    locations = [
        (home / ".claude" / "skills", None),  # Personal skills
        (Path(cwd) / ".claude" / "skills", None),  # Project skills
    ]

    # Plugin skills - search in marketplaces and cache subdirectories
    plugins_dir = home / ".claude" / "plugins"
    if plugins_dir.exists():
        for category in ["marketplaces", "cache"]:
            category_dir = plugins_dir / category
            if category_dir.exists():
                for plugin_path in category_dir.iterdir():
                    if plugin_path.is_dir():
                        # Handle cache structure: cache/name/name/version/skills/
                        if category == "cache":
                            for nested in plugin_path.iterdir():
                                if nested.is_dir():
                                    for version_dir in nested.iterdir():
                                        skills_dir = version_dir / "skills"
                                        if skills_dir.exists():
                                            locations.append((skills_dir, nested.name))
                        else:
                            # Handle marketplaces structure: marketplaces/name/skills/
                            skills_dir = plugin_path / "skills"
                            if skills_dir.exists():
                                locations.append((skills_dir, plugin_path.name))

    # Scan each location
    for skills_dir, plugin_name in locations:
        if not skills_dir.exists():
            continue

        for skill_file in skills_dir.glob("*/SKILL.md"):
            frontmatter = parse_frontmatter(skill_file)

            skills.append({
                "name": frontmatter.get("name", skill_file.parent.name),
                "description": frontmatter.get("description", ""),
                "skill_file": str(skill_file),
                "plugin_name": plugin_name
            })

    return skills


def parse_frontmatter(skill_file: str | Path) -> Dict[str, Any]:
    """Extract YAML frontmatter from SKILL.md file.

    Args:
        skill_file: Path to SKILL.md file

    Returns:
        Dict with frontmatter keys including name, description,
        user-invocable, disable-model-invocation. Empty dict if no frontmatter.
    """
    skill_path = Path(skill_file)
    if not skill_path.exists():
        return {}

    content = skill_path.read_text()

    # Match YAML frontmatter between --- delimiters
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not frontmatter_match:
        return {}

    frontmatter_text = frontmatter_match.group(1)
    frontmatter = {}

    # Parse simple key: value pairs
    for line in frontmatter_text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            # Handle boolean values
            if value.lower() in ("true", "yes"):
                value = True
            elif value.lower() in ("false", "no"):
                value = False
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            frontmatter[key] = value

    return frontmatter


def is_skill_enabled(skill_file: str | Path, plugin_name: Optional[str]) -> bool:
    """Check if a skill is enabled.

    For plugin skills:
    - Check ~/.claude/settings.json enabledPlugins for plugin_name
    - Plugin name can be "name" or "name@name" format

    For all skills:
    - Check frontmatter for "disable-model-invocation: true"
    - Check frontmatter for "user-invocable: false"

    Non-plugin skills (personal, project) are always enabled by default
    unless frontmatter disables them.

    Args:
        skill_file: Path to SKILL.md file
        plugin_name: Plugin name if this is a plugin skill, None otherwise

    Returns:
        True if skill is enabled, False if disabled
    """
    frontmatter = parse_frontmatter(skill_file)

    # Check frontmatter disable flags
    if frontmatter.get("disable-model-invocation"):
        return False

    if frontmatter.get("user-invocable") is False:
        return False

    # Non-plugin skills are enabled if frontmatter doesn't disable them
    if not plugin_name:
        return True

    # For plugin skills, check settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        # No settings file means plugin is not explicitly disabled
        return True

    try:
        settings = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return True

    enabled_plugins = settings.get("enabledPlugins", {})

    # Check both formats: "name" and "name@name"
    if plugin_name in enabled_plugins:
        return bool(enabled_plugins[plugin_name])

    plugin_at_name = f"{plugin_name}@{plugin_name}"
    if plugin_at_name in enabled_plugins:
        return bool(enabled_plugins[plugin_at_name])

    # Plugin not found in enabledPlugins - assume enabled
    return True


def debug_log(message: str) -> None:
    """Write message to debug log if SKILL_HOOK_DEBUG=1.

    Args:
        message: Message to write to log
    """
    if os.environ.get("SKILL_HOOK_DEBUG") == "1":
        log_path = Path("/tmp/hook-debug.log")
        with open(log_path, "a") as f:
            f.write(f"[{os.getpid()}] {message}\n")


def format_skill_checkpoints(skills: list, completed: list = None) -> str:
    """Generate skill activation checkpoint message.

    Args:
        skills: List of skill names
        completed: List of completed checkpoint numbers (1-4)

    Returns:
        Formatted checkpoint message string
    """
    from textwrap import dedent

    completed = completed or []
    first_skill = skills[0] if skills else "skill-name"
    skills_str = ", ".join(skills[:5])
    if len(skills) > 5:
        skills_str += f" (+{len(skills) - 5} more)"

    def mark(cp_num):
        return "✓" if cp_num in completed else "☐"

    return dedent(f"""
{mark(1)} CHECKPOINT 1 - EVALUATE SKILLS:
Use EXACT format: EVAL: [skill-name] - YES/NO/MAYBE - <one-line reason>

Detected skills: {skills_str}

{mark(2)} CHECKPOINT 2 - ASK USER (after evaluation):
Call AskUserQuestion with these options:
• {first_skill} (Recommended)
• No skill needed - <brief reason>
• Something else (custom)

{mark(3)} CHECKPOINT 3 - ACTIVATE SKILL (after user selects):
Call Skill(skill-name) tool

{mark(4)} CHECKPOINT 4 - IMPLEMENT (after skill activates):
Proceed with task implementation

CRITICAL: Do not skip checkpoints. Do not proceed until user responds to AskUserQuestion.
""").strip()


if __name__ == "__main__":
    # Simple test when run directly
    print("Hook utils module - testing functions...")

    # Test discover_skills
    skills = discover_skills(os.getcwd())
    print(f"\nFound {len(skills)} skills:")
    for skill in skills[:5]:  # Show first 5
        print(f"  - {skill['name']} ({skill['plugin_name'] or 'local'})")

    # Test is_skill_enabled on first skill
    if skills:
        first = skills[0]
        enabled = is_skill_enabled(first['skill_file'], first['plugin_name'])
        print(f"\n{first['name']} enabled: {enabled}")
