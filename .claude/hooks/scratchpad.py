import json
import sys
from textwrap import dedent

require_skill_eval_activation = dedent("""
┌─────────────────────────────────────────────────────────────────┐
│ SKILL ACTIVATION REQUIRED                                       │
└─────────────────────────────────────────────────────────────────┘

Before using tools, complete these steps:

STEP 1 - EVALUATE (output this now):
 YES/NO - [reason]

STEP 2 - CALL AskUserQuestion:
Ask which skill to activate. Options:
• using-skills (recommended)
• No skill needed
• Something else

STEP 3 - ACTIVATE:
After user selects, use Skill(tool_name) to activate.

═══════════════════════════════════════════════════════════════════
OUTPUT THE EVALUATION NOW. Then call AskUserQuestion.
═══════════════════════════════════════════════════════════════════
""").strip()

output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "decisionReason": require_skill_eval_activation,
    }
}

print(require_skill_eval_activation, file=sys.stderr)
print(json.dumps(output, ensure_ascii=False))