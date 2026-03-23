# Sample Session

## User Prompt

```
suggest 3 ideas for improving the README
```

## Hook Output (injected into system prompt)

```
SKILL CHECKPOINT: The following skills may be relevant: brainstorming

Before proceeding:
1. Evaluate each skill: EVAL: [skill-name] - YES/NO/MAYBE - <one-line reason>
2. Use AskUserQuestion to let user select
3. Call Skill() to activate
4. Only then proceed with implementation

Skills to evaluate:
- brainstorming (keywords: idea, ideas, suggest, suggestion)
```

## Claude Response

```
EVAL: [brainstorming] - YES - User is asking for ideas, which matches brainstorming skill purpose

[Uses AskUserQuestion tool with options:
- brainstorming
- No skill needed
- Something else...]

User selects: brainstorming

[Calls Skill() tool with "brainstorming"]

Now I'll help you brainstorm ideas for improving the README...
```

## State Transitions

```
Initial: {}
After UserPromptSubmit: {skills_suggested: ["brainstorming"]}
After EVAL output: {skills_suggested: ["brainstorming"], evaluation_done: true}
After AskUserQuestion: {skills_suggested: ["brainstorming"], ask_question_answered: true}
After Skill(): {skills_suggested: ["brainstorming"], activated: ["brainstorming"]}
```
