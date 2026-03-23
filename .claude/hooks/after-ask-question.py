#!/usr/bin/env python3
"""
PostToolUse hook that runs after AskQuestion tool.
Reads user's answer and updates state accordingly.

INSTALLATION (in settings.local.json):
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "AskQuestion",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/after-ask-question.py" }]
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
    if not STATE_FILE.exists():
        return {"skills_suggested": [], "selected_skill": None, "no_skill_needed": False}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, Exception):
        return {"skills_suggested": [], "selected_skill": None, "no_skill_needed": False}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def parse_input() -> dict:
    try:
        data = json.loads(sys.stdin.read())
        return {
            "tool_input": data.get("tool_input", {}),
            "tool_response": data.get("tool_response", {})
        }
    except json.JSONDecodeError:
        return {"tool_input": {}, "tool_response": {}}


def main():
    input_data = parse_input()
    tool_response = input_data.get("tool_response", {})

    if not tool_response:
        return  # No response, nothing to do

    state = load_state()

    # Check for answers in the response
    # AskUserQuestion returns {"answers": {"question": "selected_option"}}
    answers = tool_response.get("answers", {})
    if not answers:
        return

    # Get the first answer (skill selection question)
    for question_key, answer in answers.items():
        answer_lower = str(answer).lower() if answer else ""

        # Check if user selected "no skills needed"
        if "no skill" in answer_lower:
            state["no_skill_needed"] = True
            state["ask_question_answered"] = True
            save_state(state)
            return

        # Check if user selected "something else"
        if "something else" in answer_lower:
            # User wants to provide custom input, don't set skill yet
            state["ask_question_answered"] = False
            save_state(state)
            return

        # User selected a skill - extract skill name from answer
        # Answer format: "skill-name (recommended)" or "skill-name"
        skill_name = answer.split("(")[0].strip()
        if skill_name:
            state["selected_skill"] = skill_name
            state["ask_question_answered"] = True
            save_state(state)


if __name__ == "__main__":
    main()
