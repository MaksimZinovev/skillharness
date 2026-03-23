# Configuration

## settings.local.json

```json
{
  "hooks": {
    "UserPromptSubmit": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/skill-forced-eval-hook.py" }] }],
    "PreToolUse": [{ "matcher": "^(?!AskUserQuestion|Skill).*$", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/require-ask-question-first.py" }] }],
    "PostToolUse": [
      { "matcher": "AskUserQuestion", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/verify-evaluation.py" }, { "type": "command", "command": "python3 .claude/hooks/after-ask-question.py" }] },
      { "matcher": "Skill", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/track-skill-activation.py" }] }
    ],
    "Stop": [{ "matcher": "^(?!AskUserQuestion).*$", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/verify-ask-question.py" }] }]
  }
}
```

## keyword-filters.conf

```
skill-name:keyword1,keyword2,keyword3
```

Example:

```
brainstorming:idea,ideas,suggest,suggestion
testing:test,tests,testing
playwright:browser,page,click,screenshot
```
