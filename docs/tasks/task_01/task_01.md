# Task: Add `/noskill` command to bypass hooks for single prompt

## Objective

Add a `/noskill` command that allows users to bypass all skill harness hooks for a single prompt. This provides an escape hatch when the skill enforcement workflow adds too much friction for simple queries.

**Problem:** Currently, when skill harness hooks are enabled, they work well for enforcing skill evaluation. However, they block Claude even for simple questions where no skill is needed.

**Solution:** User can add `/noskill` to their prompt to completely bypass all hooks for that prompt only.

## Context

**Current behavior:** Hooks enforce skill evaluation workflow:
1. `skill-forced-eval-hook.py` discovers skills, writes to state file
2. `require-ask-question-first.py` blocks tools until workflow complete
3. Claude must evaluate skills → ask user → activate skill → implement

**Desired behavior:**

### Example 1: Default (hooks enabled)

```
User: suggest 1 idea for improving home page tests

Claude evaluates skills and outputs:

  EVAL: brainstorming - YES - User is asking for improvement ideas
  EVAL: playwright - MAYBE - Could help with test patterns
  EVAL: testing-anti-patterns - MAYBE - Could inform improvements
  EVAL: condition-based-waiting - NO - Too specific
  EVAL: circleci-cli - NO - Not related to CI

[AskUserQuestion appears, workflow continues...]
```

### Example 2: With `/noskill` bypass

```
User: suggest 1 idea for improving home page tests /noskill

Claude responds directly without skill evaluation or blocking.
Hooks detect /noskill and skip all enforcement.
Next prompt works normally (hooks re-enabled).
```

## Decisions

1. **Bypass scope:** Full bypass - no skill discovery, no blocking, Claude responds normally
2. **Duration:** Single prompt only - auto-reset, hooks re-enabled for next prompt
3. **Keyword:** Hardcoded as `/noskill` (case-insensitive)

---

## Evidence Pack

### Hook Input/Output Formats (from Claude Code docs)

| Hook Event | Input Fields | Output Format |
|------------|--------------|---------------|
| **UserPromptSubmit** | `prompt`, `cwd` | `{hookSpecificOutput: {hookEventName, additionalContext}}` |
| **PreToolUse** | `tool_name`, `tool_input` | `{hookSpecificOutput: {hookEventName, permissionDecision, decisionReason}}` |
| **Stop** | `reason`, `transcript_path` | `{decision: "approve\|block", stopReason}` |

### Existing SkillHarness Patterns

From `/Users/maksim/repos/skillharness/.claude/hooks/`:
- **State file**: `/tmp/skill-session-state.json`
- **Shared utils**: `hook_utils.py` with `debug_log()`, `format_skill_checkpoints()`
- **Python scripts**: All hooks use Python 3
- **State schema**:
```json
{
  "skills_suggested": [],
  "selected_skill": null,
  "ask_question_answered": false,
  "no_skill_needed": false,
  "activated": [],
  "prompt_count": 1
}
```

### Key Insight

The existing state already has `no_skill_needed` field! The `after-ask-question.py` sets it when user selects "No skill needed". We just need to:
1. Detect `/noskill` in `skill-forced-eval-hook.py`
2. Set `no_skill_needed: true` (same as user selecting "No skill needed")
3. Existing hooks already respect this state!

---
