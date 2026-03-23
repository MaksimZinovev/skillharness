#!/usr/bin/env python3
"""
PostToolUse hook that tracks Skill() activation.

Runs after Skill() tool is called.
Adds skill name to 'activated' array in session state.

INSTALLATION (in settings.local.json):
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/track-skill-activation.py" }]
      }
    ]
  }
}
"""

import json
import sys
from pathlib import Path

STATE_FILE = Path("/tmp/skill-session-state.json")


def load_state() -> dict:
    """Load session state from temp file."""
    if not STATE_FILE.exists():
        return {"skills_suggested": [], "activated": [], "user_confirmed_no_skill": False}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, Exception):
        return {"skills_suggested": [], "activated": [], "user_confirmed_no_skill": False}


def save_state(state: dict) -> None:
    """Persist session state to temp file."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def parse_input() -> dict:
    """Parse JSON input from stdin."""
    try:
        data = json.loads(sys.stdin.read())
        return {
            "tool_name": data.get("tool_name", ""),
            "tool_input": data.get("tool_input", {}),
            "tool_result": data.get("tool_result", "")
        }
    except json.JSONDecodeError:
        return {"tool_name": "", "tool_input": {}, "tool_result": ""}


def main():
    input_data = parse_input()
    skill_name = input_data["tool_input"].get("skill", "")

    if not skill_name:
        return  # No skill name, nothing to track

    state = load_state()
    activated = state.get("activated", [])

    # Add skill to activated list if not already there
    if skill_name not in activated:
        activated.append(skill_name)
        state["activated"] = activated
        save_state(state)


if __name__ == "__main__":
    main()
