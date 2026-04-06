# Skill Harness Process Flow Diagram

Step-by-step workflow from user prompt to implementation.

```mermaid
flowchart TD
    subgraph UserInput["User Input"]
        A[User enters prompt] --> B{Has /noskill prefix?}
        B -->|Yes| Z[Skip evaluation<br/>Direct implementation]
        B -->|No| C[Submit prompt]
    end

    subgraph HookPhase1["Hook: UserPromptSubmit"]
        C --> D[skill-forced-eval-hook.py]
        D --> E[Inject checkpoint instructions<br/>into system prompt]
        E --> F[Scan keywords against<br/>keyword-filters.conf]
    end

    subgraph EvaluationPhase["Evaluation Phase"]
        F --> G[Claude evaluates skills]
        G --> H[Output EVAL statements]
        H --> I["EVAL: brainstorming - YES - User asking for ideas"]
        H --> J["EVAL: playwright - MAYBE - Could help with tests"]
        H --> K["EVAL: circleci-cli - NO - Not related to CI"]
    end

    subgraph HookPhase2["Hook: PreToolUse"]
        I & J & K --> L{Tool != AskUserQuestion<br/>AND Tool != Skill?}
        L -->|Yes| M[require-ask-question-first.py<br/>BLOCKS tool]
        L -->|No| N[Allow tool]
        M --> O[Returns error:<br/>Must use AskUserQuestion first]
    end

    subgraph UserChoice["User Selection"]
        N --> P[Claude calls AskUserQuestion]
        P --> Q[Display skill options]
        Q --> R{User selects}
        R -->|brainstorming| S[Skill selected]
        R -->|playwright| S
        R -->|No skill needed| T[No skill flag set]
    end

    subgraph HookPhase3["Hook: PostToolUse - AskUserQuestion"]
        S --> U[verify-evaluation.py]
        U --> V[Verify EVAL pattern<br/>exists in transcript]
        V --> W[after-ask-question.py]
        W --> X[Update state file:<br/>ask_question_answered = true]
        T --> X
    end

    subgraph SkillActivation["Skill Activation"]
        X --> Y{Skill selected?}
        Y -->|Yes| AA[Claude calls Skill tool]
        AA --> AB[track-skill-activation.py]
        AB --> AC[Update state file:<br/>activated = true]
        AC --> AD[Skill content loaded]
        Y -->|No| AE[Proceed without skill]
    end

    subgraph Implementation["Implementation"]
        AD --> AF[Execute task with skill context]
        AE --> AF
        Z --> AF
        AF --> AG[Task complete]
    end

    subgraph HookPhase4["Hook: Stop"]
        AG --> AH{Workflow complete?}
        AH -->|No| AI[verify-ask-question.py<br/>BLOCKS stop]
        AH -->|Yes| AJ[Session can end]
    end

    style A fill:#e1f5fe,color:#0d47a1
    style Z fill:#fff3e0,color:#e65100
    style I fill:#c8e6c9,color:#1b5e20
    style J fill:#fff9c4,color:#f57f17
    style K fill:#ffcdd2,color:#b71c1c
    style M fill:#c62828,color:#fff
    style O fill:#c62828,color:#fff
    style AA fill:#bbdefb,color:#0d47a1
    style AD fill:#c8e6c9,color:#1b5e20
    style AF fill:#e1bee7,color:#4a148c
```

## Example Flow (from SAMPLE_SESSION.md)

```
User: suggest 1 idea for improving home page tests

                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Claude evaluates skills and outputs:                            │
│                                                                 │
│   EVAL: brainstorming - YES - User is asking for improvement   │
│   EVAL: playwright - MAYBE - Could help with test patterns     │
│   EVAL: testing-anti-patterns - MAYBE - Could inform           │
│   EVAL: condition-based-waiting - NO - Too specific            │
│   EVAL: circleci-cli - NO - Not related to CI                  │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ AskUserQuestion: Which skill should I use?                      │
│                                                                 │
│ Options:                                                        │
│ • brainstorming (Recommended)                                   │
│ • playwright skill                                              │
│ • No skill needed                                               │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ User selects: brainstorming (Recommended)                       │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Skill(brainstorming) activated                                  │
│                                                                 │
│ Claude follows brainstorming workflow:                          │
│ • Phase 1: Understanding - asks clarifying questions            │
│ • Phase 2: Exploration - proposes approaches                    │
│ • Phase 3: Design - presents solution incrementally             │
└─────────────────────────────────────────────────────────────────┘
                    ↓
               Implementation
```

## Hook Execution Order

| Event | Hook File | Purpose |
|-------|-----------|---------|
| `UserPromptSubmit` | `skill-forced-eval-hook.py` | Inject evaluation instructions |
| `PreToolUse` | `require-ask-question-first.py` | Block tools until AskUserQuestion used |
| `PostToolUse` (Ask) | `verify-evaluation.py` | Confirm EVAL pattern exists |
| `PostToolUse` (Ask) | `after-ask-question.py` | Update state from user answer |
| `PostToolUse` (Skill) | `track-skill-activation.py` | Record activated skill |
| `Stop` | `verify-ask-question.py` | Block stop until workflow complete |
