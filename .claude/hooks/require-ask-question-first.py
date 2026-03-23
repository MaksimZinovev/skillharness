#!/usr/bin/env python3
"""
PreToolUse hook that blocks all tools except AskQuestion until skill selection is complete.

INSTALLATION (in settings.local.json):
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^(?!AskQuestion).*$",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/require-ask-question-first.py" }]
      }
    ]
  }
}
"""

import json
import os
from pprint import pprint
import sys
from textwrap import dedent
import traceback
from pathlib import Path


# Import debug_log from hook_utils
try:
    from hook_utils import debug_log, format_skill_checkpoints
except ImportError:
    def debug_log(msg):
        if os.environ.get("SKILL_HOOK_DEBUG") == "1":
            with open("/tmp/hook-debug.log", "a") as f:
                f.write(f"[{os.getpid()}] {msg}\n")

def log_error(msg):
    """Log error to debug file and stderr."""
    debug_log(f"ERROR: {msg}")
    print(f"Hook error: {msg}", file=sys.stderr)

STATE_FILE = Path("/tmp/skill-session-state.json")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"skills_suggested": [], "ask_question_answered": False}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, Exception):
        return {"skills_suggested": [], "ask_question_answered": False}


def parse_input() -> dict:
    """Parse stdin JSON input from Claude Code."""
    try:
        return json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return {}

def main():
    # Parse stdin input
    data = parse_input()
    tool_name = data.get("tool_name", "")

    debug_log(f"=== PRETOOLUSE HOOK === tool={tool_name}")

    state = load_state()

    skills_suggested = state.get("skills_suggested", [])
    ask_question_answered = state.get("ask_question_answered", False)
    no_skill_needed = state.get("no_skill_needed", False)
    skill_activated = state.get("activated", [])

    debug_log(f"Skills suggested: {skills_suggested[:3]}...")
    debug_log(f"AskQuestion answered: {ask_question_answered}")

    # No skills suggested → allow all tools
    if not skills_suggested:
        debug_log("No skills - ALLOW")
        output = {"continue": True, "suppressOutput": True}
        json.dump(output, sys.stdout)
        return

    # AskQuestion answered OR skill activated OR no skill needed → allow all tools
    if ask_question_answered or skill_activated or no_skill_needed:
        debug_log("Question answered or skill activated - ALLOW")
        output = {"continue": True, "suppressOutput": True}
        json.dump(output, sys.stdout)
        return

    # Skills suggested, AskQuestion not answered → BLOCK with formatted "tool result"
    debug_log("Skills suggested but no answer - BLOCK")

    # Use shared checkpoint message
    checkpoint_msg = format_skill_checkpoints(skills_suggested)

    output = {
      "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "decisionReason": checkpoint_msg
    }
    }
    debug_log(f"PreToolUse hook output: {json.dumps(output, ensure_ascii=False)}")
    json.dump(output, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"Exception in require-ask-question-first.py: {e}")
        traceback.print_exc(file=sys.stderr)
        # Return safe default - allow tool
        json.dump({"continue": True, "suppressOutput": True}, sys.stdout)
