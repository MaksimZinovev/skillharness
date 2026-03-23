#!/usr/bin/env python3
"""
Stop Hook - Verifies AskQuestion was used before stopping.

Checks if FORCED TASK instruction was given but AskQuestion not used.
If so, BLOCKS the stop and forces AI to continue.

============================================================================
HOW TO TEST
============================================================================

HOOK_PATH=".claude/hooks/verify-ask-question.py"

1. Test with skills suggested but no AskQuestion - should BLOCK
   Command: echo '{"transcript_path":"/tmp/test-transcript.txt"}' | python3 $HOOK_PATH
   Setup: Create transcript with "FORCED TASK: Use AskQuestion tool NOW" but no "AskQuestion"
   Expected: {"decision": "block", "reason": "..."}

2. Test with AskQuestion used - should APPROVE
   Command: echo '{"transcript_path":"/tmp/test-transcript.txt"}' | python3 $HOOK_PATH
   Setup: Create transcript with "AskQuestion" tool call
   Expected: {"decision": "approve"}

3. Test with no FORCED TASK - should APPROVE
   Command: echo '{"transcript_path":"/tmp/test-transcript.txt"}' | python3 $HOOK_PATH
   Setup: Create transcript without FORCED TASK instruction
   Expected: {"decision": "approve"}

4. Debug mode
   Command: SKILL_HOOK_DEBUG=1 echo '{"transcript_path":"/tmp/test-transcript.txt"}' | python3 $HOOK_PATH

============================================================================
"""

import json
import os
from pprint import pprint
import re
import sys
from textwrap import dedent
import traceback
from pathlib import Path





# Import from hook_utils.py in the same directory
try:
    from hook_utils import debug_log
except ImportError:
    def debug_log(msg):
        if os.environ.get("SKILL_HOOK_DEBUG") == "1":
            with open("/tmp/hook-debug.log", "a") as f:
                f.write(f"[{os.getpid()}] {msg}\n")

def log_error(msg):
    """Log error to debug file and stderr."""
    debug_log(f"ERROR: {msg}")
    print(f"Hook error: {msg}", file=sys.stderr)


def check_state_file() -> dict:
    """Read session state file.

    Returns:
        Dict with skills_suggested, ask_question_answered, etc.
    """
    state_file = Path("/tmp/skill-session-state.json")
    if not state_file.exists():
        return {}

    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def main():
    """Stop hook main entry point."""
    # Parse input from stdin
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    debug_log("=== STOP HOOK ===")

    state = check_state_file()
    skills_suggested = state.get("skills_suggested", [])
    ask_question_answered = state.get("ask_question_answered", False)
    no_skill_needed = state.get("no_skill_needed", False)
    activated = state.get("activated", [])

    debug_log(f"Skills suggested: {skills_suggested}")
    debug_log(f"AskQuestion answered: {ask_question_answered}")
    debug_log(f"No skill needed: {no_skill_needed}")
    debug_log(f"Activated: {activated}")

    # If no skills were suggested, approve stop
    if not skills_suggested:
        debug_log("No skills suggested - APPROVE")
        output = {"decision": "approve"}
        json.dump(output, sys.stdout)
        return

    # If AskQuestion answered OR no skill needed OR skill activated, approve stop
    if ask_question_answered or no_skill_needed or activated:
        debug_log("AskQuestion answered - APPROVE")
        output = {"decision": "approve"}
        json.dump(output, sys.stdout)
        return

    # Skills were suggested but AskQuestion not answered - BLOCK
    debug_log("AskQuestion NOT answered - BLOCK")

    # Use shared checkpoint message
    from hook_utils import format_skill_checkpoints
    checkpoint_msg = format_skill_checkpoints(skills_suggested)

    output = {
    "continue": False,
    "stopReason": checkpoint_msg,
    "decision": "block"}

    debug_log(f"Stop hook output: {json.dumps(output, ensure_ascii=False)}")
    json.dump(output, sys.stdout)



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"Exception in verify-ask-question.py: {e}")
        traceback.print_exc(file=sys.stderr)
        # Return safe default - approve stop
        json.dump({"decision": "approve"}, sys.stdout)
