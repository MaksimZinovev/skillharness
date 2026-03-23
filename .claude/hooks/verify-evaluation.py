#!/usr/bin/env python3
"""
PostToolUse hook for AskUserQuestion - Verifies evaluation was done.

Checks if the AI output the evaluation pattern before AskUserQuestion.
Pattern: [skill-name] - YES/NO - [reason]

If evaluation not found, blocks and asks AI to output evaluation first.
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

# Import debug_log from hook_utils
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

STATE_FILE = Path("/tmp/skill-session-state.json")


def load_state() -> dict:
    """Load session state."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, Exception):
        return {}


def save_state(state: dict):
    """Save session state atomically."""
    TEMP_FILE = STATE_FILE.with_suffix('.tmp')
    with open(TEMP_FILE, 'w') as f:
        f.write(json.dumps(state, indent=2))
        f.flush()
        os.fsync(f.fileno())
    TEMP_FILE.rename(STATE_FILE)


def check_evaluation_in_transcript(transcript_path: str, skills: list) -> bool:
    """Check if evaluation pattern exists in transcript.

    Pattern: EVAL: [skill-name] - YES/NO/MAYBE - <one-line reason>

    =========================================================================
    DETECTION EXAMPLES - What will be detected:
    =========================================================================

    VALID (will be detected):
    -------------------------
    EVAL: [playwright] - YES - browser testing needed
    EVAL: [playwright] - NO - not relevant
    EVAL: [playwright] - MAYBE - unsure if needed
    EVAL: [brainstorming] - YES - ideation task
    EVAL: [playwright]-YES-reason  (no spaces OK)
    eval: [PLAYWRIGHT] - maybe - case insensitive

    INVALID (will NOT be detected):
    -------------------------------
    [playwright] - YES - reason  (missing EVAL: prefix)
    playwright - YES - reason  (missing EVAL: and brackets)
    EVAL [playwright] YES reason  (missing colon and dashes)
    EVAL: [playwright] - UNSURE - reason  (invalid decision)

    =========================================================================
    """
    if not transcript_path:
        return False

    try:
        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            debug_log(f"Transcript file not found: {transcript_path}")
            return False

        content = transcript_file.read_text()

        # Pattern requires EVAL: prefix, brackets, YES/NO, and dash
        # EVAL: [skill-name] - YES/NO - reason

        found_evaluations = []

        for skill in skills[:5]:  # Check first 5 skills
            escaped_skill = re.escape(skill)

            # Pattern variants - must have EVAL: prefix, brackets, YES/NO/MAYBE, and dash
            patterns = [
                # Standard: EVAL: [skill] - YES/NO/MAYBE - reason
                rf'EVAL:\s*\[{escaped_skill}\]\s*-\s*(YES|NO|MAYBE)\s*-',
                # Compact: EVAL:[skill]-YES/NO/MAYBE-reason
                rf'EVAL:\s*\[{escaped_skill}\]-(YES|NO|MAYBE)-',
                # Case insensitive prefix: eval: [skill] - yes/no/maybe -
                rf'eval:\s*\[{escaped_skill}\]\s*-\s*(YES|NO|MAYBE)\s*-',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
                if match:
                    decision = match.group(1).upper()
                    found_evaluations.append(f"{skill}:{decision}")
                    debug_log(f"Found evaluation for: {skill} ({decision})")
                    break  # Found one pattern for this skill, move to next

        if found_evaluations:
            debug_log(f"All evaluations found: {', '.join(found_evaluations)}")
            return True

        debug_log("No evaluation pattern found in transcript")
        return False

    except Exception as e:
        debug_log(f"Error reading transcript: {e}")
        return False


def main():
    """PostToolUse hook main entry point."""
    # Parse stdin input
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    tool_name = data.get("tool_name", "")
    tool_response = data.get("tool_response", {})
    transcript_path = data.get("transcript_path", "")

    debug_log(f"=== VERIFY EVALUATION === tool={tool_name}")

    # Load state
    state = load_state()
    skills_suggested = state.get("skills_suggested", [])

    if not skills_suggested:
        debug_log("No skills suggested - approve")
        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
        json.dump(output, sys.stdout)
        return

    # Check if evaluation exists in transcript
    evaluation_found = check_evaluation_in_transcript(transcript_path, skills_suggested)

    if evaluation_found:
        debug_log("Evaluation found - approve")

        # Update state: mark evaluation as done
        state["evaluation_completed"] = True

        # Check if user answered AskUserQuestion
        answers = tool_response.get("answers", {})
        if answers:
            state["ask_question_answered"] = True
            debug_log(f"AskUserQuestion answered: {answers}")

        save_state(state)

        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
        json.dump(output, sys.stdout)
    else:
        debug_log("Evaluation NOT found - block")

        skills_str = ", ".join(skills_suggested[:3])

        output = {
            "decision": "block",
            "reason": f"Output evaluation first before using AskUserQuestion.\n\n"
                     f"Required format: EVAL: [skill-name] - YES/NO/MAYBE - <one-line reason>\n\n"
                     f"Skills to evaluate: {skills_str}\n\n"
                     f"Example:\n"
                     f"EVAL: [{skills_suggested[0] if skills_suggested else 'skill'}] - YES - this task involves testing\n"
                     f"EVAL: [another-skill] - NO - not relevant"
        }
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"Exception in verify-evaluation.py: {e}")
        traceback.print_exc(file=sys.stderr)
        # Return safe default - approve
        json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse"}}, sys.stdout)
