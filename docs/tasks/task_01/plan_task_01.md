# Task: Add `/noskill` command to bypass hooks for single prompt

## Objective

Add a `/noskill` command that allows users to bypass all skill harness hooks for a single prompt. This provides an escape hatch when the skill enforcement workflow adds too much friction for simple queries.

**Problem:** Currently, when skill harness hooks are enabled, they work well for enforcing skill evaluation. However, they block Claude even for simple questions where no skill is needed.

**Solution:** User can type `/noskill` followed by their prompt to completely bypass all hooks for that prompt only.

## Context

**Current behavior:** Hooks enforce skill evaluation workflow:
1. `skill-forced-eval-hook.py` discovers skills, writes to state file
2. `require-ask-question-first.py` blocks tools until workflow complete
3. Claude must evaluate skills, ask user, activate skill, implement

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
User: /noskill what time is it?

Claude responds directly without skill evaluation or blocking.
Slash command sets state BEFORE hooks run.
Hooks see no_skill_needed: true, skip all enforcement.
Next prompt works normally (hooks re-enabled).
```

## Decisions

1. **Bypass scope:** Full bypass - no skill discovery, no blocking, Claude responds normally
2. **Duration:** Single prompt only - auto-reset, hooks re-enabled for next prompt
3. **Trigger:** Slash command `/noskill` (not inline text detection)

---

## Evidence Pack

### Hook Input/Output Formats (from Claude Code docs)

| Hook Event | Input Fields | Output Format |
|------------|--------------|---------------|
| **UserPromptSubmit** | `prompt`, `cwd` | `{hookSpecificOutput: {hookEventName, additionalContext}}` |
| **PreToolUse** | `tool_name`, `tool_input` | `{hookSpecificOutput: {hookEventName, permissionDecision, decisionReason}}` |
| **Stop** | `reason`, `transcript_path` | `{decision: "approve\|block", stopReason}`` |

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
1. Create `/noskill` slash command that sets `no_skill_needed: true` BEFORE the UserPromptSubmit hook runs
2. Existing hooks already respect this state!

---

## Critical Analysis: Slash Command vs. Inline Detection

### Why Slash Command Approach is Better

| Aspect | Inline Detection (Original Plan) | Slash Command (New Plan) |
|--------|------------------------------|------------------------|
| Regex reliability | `\b/noskill\b` - `/` breaks word boundary | No regex needed - command is explicitly invoked |
| Timing | Hook runs FIRST, then must parse prompt | Command runs FIRST, sets state, hook sees state |
| Edge cases | `/noskillish` - might false match | No ambiguity - `/noskill` is explicit |
| Maintenance | Fragile regex in hook code | Command is simple, isolated |

### How Slash Commands Work in Claude Code

From documentation and code analysis:

 When a user types `/noskill what time is it?`:

1. **Command execution happens FIRST**: Claude Code recognizes the slash command and loads it command file
2. **Command can use Bash tool**: Commands have `allowed-tools` including Bash
3. **Command outputs become the prompt**: The command's instructions become the prompt that the UserPromptSubmit hook sees
4. **Hook runs with modified prompt**: The UserPromptSubmit hook sees the output of the slash command, not the original user input

 **CRITICAL: The command MUST set state BEFORE the hook processes the prompt.** This is achieved by:
- Command writes state file at the very start of its instructions
- Command outputs instructions for Claude (which becomes the prompt)
- Hook reads state file and sees `no_skill_needed: true`

---

## Implementation Plan

### Step 1: Create `/noskill` Slash Command

**File**: `.claude/commands/noskill.md`

**Purpose**: Use the `` !`<command>` `` syntax to set `no_skill_needed: true` in state file **before** any hooks process the prompt.

**Critical Mechanism**: The `` !`...` `` syntax runs shell commands during preprocessing, BEFORE the skill content is sent to Claude (and BEFORE hooks run). This is documented at https://code.claude.com/docs/en/skills#advanced-patterns

```markdown
---
description: Bypass skill harness hooks for this prompt only
argument-hint: <your prompt here>
---

!`python3 -c "
import json
from pathlib import Path
state_file = Path('/tmp/skill-session-state.json')
existing = {}
if state_file.exists():
    try:
        existing = json.loads(state_file.read_text())
    except:
        pass
state = {
    'skills_suggested': [],
    'selected_skill': None,
    'ask_question_answered': False,
    'no_skill_needed': True,
    'activated': [],
    'prompt_count': existing.get('prompt_count', 0) + 1
}
Path('/tmp/skill-session-state.tmp').write_text(json.dumps(state, indent=2))
Path('/tmp/skill-session-state.tmp').rename(state_file)
"`

$ARGUMENTS
```

**How this works:**

1. User types `/noskill what time is it?`
2. `` !`python3 ...` `` executes **during preprocessing** (before hooks)
3. State file is written with `no_skill_needed: true`
4. Preprocessed content (`$ARGUMENTS` → "what time is it?") becomes the prompt
5. UserPromptSubmit hook runs, reads state, sees `no_skill_needed: true`
6. Hook skips skill discovery, outputs empty additionalContext
7. Claude responds normally
8. Next prompt: hook resets state with `no_skill_needed: false`

### Step 2: Modify `skill-forced-eval-hook.py` to Check State FIRST

**File**: `.claude/hooks/skill-forced-eval-hook.py`

**Change**: Add state check at the beginning of `main()` function, BEFORE any skill discovery.

**Add after line 197 (after `if not prompt:` check):**

```python
    # ============================================================================
    # STATE CHECK - If /noskill command already set bypass state
    # ============================================================================
    STATE_FILE = Path("/tmp/skill-session-state.json")

    if STATE_FILE.exists():
        try:
            existing_state = json.loads(STATE_FILE.read_text())
            if existing_state.get("no_skill_needed", False):
                debug_log("Bypass state already set by /noskill command - skipping skill discovery")
                # Output empty additionalContext (no skill guidance)
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": ""
                    }
                }
                json.dump(output, sys.stdout)
                return
        except (json.JSONDecodeError, Exception):
            pass  # Continue with normal flow if state file is corrupted

    # ============================================================================
    # NORMAL FLOW - Discover and filter skills (existing code continues)
    # ============================================================================
```

**Why this is needed**: The slash command's `` !`...` `` preprocessing runs before hooks, writing the bypass state. The hook must check for this existing state FIRST, otherwise it would overwrite the state with default values and undo the bypass.

**IMPORTANT**: Remove any existing `/noskill` inline regex detection code that was previously added, since we now use the slash command approach instead.

### Step 3: No changes needed to other hooks!

The existing hooks already respect `no_skill_needed: true`. We just need to set it via the slash command.

### Step 4: Update documentation

**Files to update**:
1. `README.md` - Add `/noskill` usage section
2. `docs/SAMPLE_SESSION.md` - Add bypass example

---

## Verification Criteria

### Functional Requirements

- [ ] `/noskill <prompt>` -> no skill discovery, no blocking, Claude responds normally
- [ ] Without `/noskill` -> normal skill evaluation workflow
- [ ] Bypass only affects current prompt (next prompt works normally)
- [ ] State is set by command BEFORE hooks run

### State Verification at Each Hook Lifecycle Stage

| Hook Stage | Hook File | Expected State (with `/noskill`) | Expected State (without `/noskill`) |
|------------|-----------|----------------------------------|-------------------------------------|
| **0. Slash Command** | `noskill.md` (runs FIRST) | `no_skill_needed: true`, `skills_suggested: []` | N/A - command not invoked |
| **1. UserPromptSubmit** | `skill-forced-eval-hook.py` | Reads `no_skill_needed: true` → skips discovery | `no_skill_needed: false`, `skills_suggested: [...]` |
| **2. PreToolUse** | `require-ask-question-first.py` | Reads `no_skill_needed: true` → allows all tools immediately | Reads `no_skill_needed: false` → blocks until workflow complete |
| **3. PostToolUse (Ask)** | `after-ask-question.py` | Not triggered (no AskUserQuestion needed) | Reads user selection, sets `ask_question_answered: true` or `no_skill_needed: true` |
| **4. PostToolUse (Skill)** | `track-skill-activation.py` | Not triggered (no Skill tool needed) | Appends to `activated: [...]` list |
| **5. Stop** | `verify-ask-question.py` | Reads `no_skill_needed: true` → allows stop | Reads `ask_question_answered: true` or `activated: [...]` → allows stop |
| **6. Next Prompt** | `skill-forced-eval-hook.py` | `no_skill_needed: false` (reset), `prompt_count: N+1` | Normal behavior |

### State File Schema

```json
{
  "skills_suggested": ["skill1", "skill2"],
  "selected_skill": null,
  "ask_question_answered": false,
  "no_skill_needed": false,
  "activated": [],
  "prompt_count": 1
}
```

### Verification Checklist by Component

#### Command: `noskill.md`
- [ ] Sets `no_skill_needed: true` in state file at startup
- [ ] Increments `prompt_count`
- [ ] Outputs `$ARGUMENTS` as the prompt for Claude
- [ ] Works with empty arguments (shows usage hint)
- [ ] Works with arguments (passes them through)

#### Hook 1: `skill-forced-eval-hook.py` (UserPromptSubmit)
- [ ] Checks state file at the beginning
- [ ] If `no_skill_needed: true` → outputs empty additionalContext and returns
- [ ] If `no_skill_needed: false` → continues with normal skill discovery
- [ ] Logs: "Bypass state already set by /noskill command" (when debug enabled)
- [ ] REMOVED: Old inline `/noskill` regex detection code

#### Hook 2: `require-ask-question-first.py` (PreToolUse)
- [ ] Reads state file
- [ ] If `no_skill_needed: true` → returns `{continue: true, suppressOutput: true}`
- [ ] If `no_skill_needed: false` AND `skills_suggested: []` → allows tools (no skills matched)
- [ ] If `no_skill_needed: false` AND `skills_suggested: [...]` → blocks with checkpoint message

#### Hook 3: `after-ask-question.py` (PostToolUse - AskQuestion)
- [ ] Not triggered when `/noskill` used (Claude doesn't call AskUserQuestion)
- [ ] Normal flow: reads user answer, updates `ask_question_answered` or `no_skill_needed`

#### Hook 4: `track-skill-activation.py` (PostToolUse - Skill)
- [ ] Not triggered when `/noskill` used (Claude doesn't call Skill)
- [ ] Normal flow: appends skill name to `activated` list

#### Hook 5: `verify-ask-question.py` (Stop)
- [ ] Reads state file
- [ ] If `no_skill_needed: true` → allows stop (returns `{decision: "approve"}`)
- [ ] If `ask_question_answered: true` → allows stop
- [ ] If `activated: [...]` (non-empty) → allows stop
- [ ] Otherwise → blocks stop with message

#### Hook 6: State Reset (Next UserPromptSubmit)
- [ ] New prompt resets `no_skill_needed: false` (by default state initialization)
- [ ] `prompt_count` increments (can be used to detect new prompt)
- [ ] Previous state fully cleared for fresh evaluation

---

## Verification Instructions

```bash
# ============================================================================
# SETUP
# ============================================================================
cd /Users/maksim/repos/skillharness
export SKILL_HOOK_DEBUG=1
STATE_FILE="/tmp/skill-session-state.json"

# Helper to check state
state() { echo "=== STATE ===" && cat $STATE_FILE 2>/dev/null | python3 -m json.tool || echo "No state file"; }

# ============================================================================
# STEP 1: Create the slash command file
# ============================================================================

# Check if commands directory exists
ls -la .claude/commands/ 2>/dev/null || mkdir -p .claude/commands

# Create the noskill command (the actual file will be created in implementation)
# For now, verify the directory structure is correct

# ============================================================================
# STEP 2: Test Hook 1 - State check at beginning
# ============================================================================

# Test 2a: Simulate slash command setting state FIRST
# Manually set bypass state (simulating what the command would do)
echo '{"prompt":"what time is it?","cwd":"/tmp"}' > /tmp/test-sim-state.json
python3 -c "
import json
from pathlib import Path
state_file = Path('/tmp/skill-session-state.json')
state_file.write_text(json.dumps({
    'skills_suggested': [],
    'selected_skill': None,
    'ask_question_answered': False,
    'no_skill_needed': True,
    'activated': [],
    'prompt_count': 1
}, indent=2))
"
# Now run the hook - it should detect the bypass state
echo '{"prompt":"what time is it?","cwd":"/tmp"}' | python3 .claude/hooks/skill-forced-eval-hook.py
state
# Expected: Hook respects existing state, outputs empty additionalContext

# Test 2b: Without bypass state → normal skill discovery
rm -f $STATE_FILE
echo '{"prompt":"help debug playwright test","cwd":"/tmp"}' | python3 .claude/hooks/skill-forced-eval-hook.py
state
# Expected: "no_skill_needed": false, "skills_suggested": ["playwright", ...]

# ============================================================================
# STEP 3: Test Hook 2 - PreToolUse respects bypass
# ============================================================================

# Test 3a: Bypass state → tools allowed
# Set bypass state first
python3 -c "
import json
from pathlib import Path
Path('/tmp/skill-session-state.json').write_text(json.dumps({
    'skills_suggested': [],
    'no_skill_needed': True,
    'ask_question_answered': False,
    'activated': [],
    'prompt_count': 1
}, indent=2))
"
echo '{"tool_name":"Bash","tool_input":{"command":"echo test"}}' | python3 .claude/hooks/require-ask-question-first.py
# Expected: {"continue": true, "suppressOutput": true}

# Test 3b: Normal state with skills → tools blocked
echo '{"prompt":"debug playwright test","cwd":"/tmp"}' | python3 .claude/hooks/skill-forced-eval-hook.py
echo '{"tool_name":"Bash","tool_input":{"command":"echo test"}}' | python3 .claude/hooks/require-ask-question-first.py
# Expected: {"hookSpecificOutput": {"permissionDecision": "deny", ...}}

# Test 3c: No skills matched → tools allowed
echo '{"prompt":"what time is it?","cwd":"/tmp"}' | python3 .claude/hooks/skill-forced-eval-hook.py
echo '{"tool_name":"Bash","tool_input":{"command":"echo test"}}' | python3 .claude/hooks/require-ask-question-first.py
# Expected: {"continue": true, "suppressOutput": true}

# ============================================================================
# STEP 4: Test Hook 5 - Stop respects bypass
# ============================================================================

# Test 4a: Bypass state → stop allowed
python3 -c "
import json
from pathlib import Path
Path('/tmp/skill-session-state.json').write_text(json.dumps({
    'skills_suggested': [],
    'no_skill_needed': True,
    'ask_question_answered': False,
    'activated': [],
    'prompt_count': 1
}, indent=2))
"
echo '{}' | python3 .claude/hooks/verify-ask-question.py
# Expected: {"decision": "approve"}

# Test 4b: Normal state, workflow incomplete → stop blocked
echo '{"prompt":"debug playwright test","cwd":"/tmp"}' | python3 .claude/hooks/skill-forced-eval-hook.py
echo '{}' | python3 .claude/hooks/verify-ask-question.py
# Expected: {"decision": "block", ...}

# ============================================================================
# STEP 5: Test State Reset
# ============================================================================

# Set bypass state
python3 -c "
import json
from pathlib import Path
Path('/tmp/skill-session-state.json').write_text(json.dumps({
    'skills_suggested': [],
    'no_skill_needed': True,
    'ask_question_answered': False,
    'activated': [],
    'prompt_count': 1
}, indent=2))
"
state
# Expected: "no_skill_needed": true

# Next prompt should reset (no_skill_needed defaults to false)
echo '{"prompt":"help me with something","cwd":"/tmp"}' | python3 .claude/hooks/skill-forced-eval-hook.py
state
# Expected: "no_skill_needed": false, "prompt_count": incremented

# ============================================================================
# END-TO-END TEST (manual in Claude Code)
# ============================================================================

# 1. Create the noskill.md command file in .claude/commands/
# 2. Enable hooks in settings.local.json
# 3. Start Claude Code session
# 4. Send: "/noskill what is 2+2?"
#    Expected: Claude responds immediately with answer, no skill evaluation
# 5. Send: "suggest 1 idea for improving tests"
#    Expected: Claude evaluates skills, shows EVAL output, asks which skill to use
# 6. Verify /tmp/hook-debug.log shows hook execution traces
```

---

## Risk Analysis

| Risk | Mitigation | Severity |
|------|------------|----------|
| Command file not found | Add to README installation instructions | Low |
| Hook overwrites state | Hook checks state FIRST, before writing | Medium |
| State not resetting | `prompt_count` increments each prompt, state defaults `no_skill_needed: false` | Low |
| Multiple `/noskill` in session | Each invocation is independent, state resets each time | Low |
| Command runs but state write fails | Use atomic write pattern (temp file + rename) | Medium |

## Open Questions

1. **Timing guarantee**: Does the slash command definitely run before UserPromptSubmit hooks? Based on Claude Code architecture, yes - commands are processed before hooks.

2. **State file race condition**: What if the hook reads state before command writes it This is unlikely because:
   - Commands run synchronously before hooks
   - The hook checks state at the beginning and returns early if bypass is set
   - Even if there's a race, the hook will see the state on subsequent reads

3. **Empty arguments**: What if user just types `/noskill` with no arguments? The command should show usage help.

## Estimated Changes

- **1 file created**: `.claude/commands/noskill.md` (~50 lines)
- **1 file modified**: `skill-forced-eval-hook.py` (~25 lines added, ~45 lines removed)
- **2 files updated**: `README.md`, `SAMPLE_SESSION.md` (documentation)
- **Total LOC**: ~80 lines (net reduction due to removing inline detection code)
