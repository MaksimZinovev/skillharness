# Skill Harness State Diagram

State machine for the skill evaluation and activation workflow.

```mermaid
stateDiagram-v2
    [*] --> Idle: Session Start

    Idle --> Evaluating: User Prompt Submitted

    state Evaluating {
        [*] --> DetectingKeywords
        DetectingKeywords --> GeneratingEVALs
        GeneratingEVALs --> [*]
    }

    Evaluating --> AwaitingUserChoice: EVALs Output

    state AwaitingUserChoice {
        [*] --> AskQuestionSent
        AskQuestionSent --> WaitingForSelection
        WaitingForSelection --> [*]: User Selects
    }

    AwaitingUserChoice --> SkillActivating: User Selects Skill
    AwaitingUserChoice --> Implementing: User Selects "No Skill"

    state SkillActivating {
        [*] --> SkillToolCalled
        SkillToolCalled --> SkillLoaded
        SkillLoaded --> [*]
    }

    SkillActivating --> Implementing: Skill Active

    Implementing --> Idle: Task Complete

    note right of Idle
        State: skills_suggested = false
        ask_question_answered = false
        no_skill_needed = false
        activated = false
    end note

    note right of Evaluating
        Hook: skill-forced-eval-hook.py
        Injects checkpoint instructions
        into system prompt
    end note

    note right of AwaitingUserChoice
        Hook: require-ask-question-first.py
        Blocks other tools until
        AskUserQuestion used
    end note

    note right of SkillActivating
        Hooks: verify-evaluation.py
               after-ask-question.py
               track-skill-activation.py
        Updates state file
    end note
```

## State Descriptions

| State | Description | State File Values |
|-------|-------------|-------------------|
| **Idle** | Waiting for user input | All flags `false` |
| **Evaluating** | Detecting skills from keywords, generating EVAL outputs | `skills_suggested` → `true` |
| **AwaitingUserChoice** | AskUserQuestion displayed, waiting for user selection | `ask_question_answered` → `true` after selection |
| **SkillActivating** | Skill tool called, skill content loaded | `activated` → `true` |
| **Implementing** | Task execution with active skill | Active skill context loaded |

## Transitions

1. **User Prompt** → Triggers `UserPromptSubmit` hook → Injects evaluation instructions
2. **EVAL Output** → Claude outputs skill evaluations → Must use AskUserQuestion
3. **User Selection** → Updates state file → Allows Skill tool or direct implementation
4. **Skill Activation** → Loads skill context → Proceeds with task
