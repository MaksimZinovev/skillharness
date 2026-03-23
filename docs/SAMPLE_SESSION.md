# Sample Session

## User Prompt

```
suggest 3 ideas for improving the README
```

## Hook Output (injected into system prompt)

## Sample Session

Here's what the workflow looks like from a user's perspective:

```
┌─────────────────────────────────────────────────────────────────┐
│ User: suggest 1 idea for improving home page tests              │
└─────────────────────────────────────────────────────────────────┘

Claude evaluates skills and outputs:

  EVAL: brainstorming - YES - User is asking for improvement ideas
  EVAL: playwright - MAYBE - Could help with test patterns
  EVAL: testing-anti-patterns - MAYBE - Could inform improvements
  EVAL: condition-based-waiting - NO - Too specific
  EVAL: circleci-cli - NO - Not related to CI

┌─────────────────────────────────────────────────────────────────┐
│ AskUserQuestion: Which skill should I use?                      │
│                                                                 │
│ Options:                                                        │
│ • brainstorming (Recommended)                                   │
│ • playwright skill                                              │
│ • No skill needed                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ User selects: brainstorming (Recommended)                       │
└─────────────────────────────────────────────────────────────────┘

Claude activates skill:

  Skill(brainstorming)

┌─────────────────────────────────────────────────────────────────┐
│ Skill activated: Brainstorming skill loaded                     │
│                                                                 │
│ Claude now follows the brainstorming workflow:                  │
│ • Phase 1: Understanding - asks clarifying questions            │
│ • Phase 2: Exploration - proposes approaches                    │
│ • Phase 3: Design - presents solution incrementally             │
└─────────────────────────────────────────────────────────────────┘

Claude proceeds with task implementation...
```