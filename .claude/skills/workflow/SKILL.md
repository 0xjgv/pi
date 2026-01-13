---
name: workflow (π)
description: Orchestrate autonomous research -> design -> execute workflows. Use when given a development task that requires understanding the codebase, planning, and implementing changes.
---

# Autonomous Development Workflow

Run workflow stages in isolated SDK sessions. Each stage runs in its own context, keeping your main context clean.

**Prerequisite**: Project must have `/1_research_codebase`, `/2_create_plan`, `/3_review_plan`, `/4_iterate_plan`, `/5_implement_plan`, and `/6_commit` commands.

## Stage 1: Research

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" --stage research
```

Read the output. Look for:

- The research document path (e.g., `thoughts/shared/research/YYYY-MM-DD-*.md`)
- Whether implementation is needed (look for "no implementation needed" or similar)

If no implementation needed, stop and report findings to user.

## Stage 2: Design

Run these sequentially, checking output between each step.

### 2a. Create Plan

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" --stage create_plan --research-doc "RESEARCH_PATH"
```

Look for the plan document path (e.g., `thoughts/shared/plans/YYYY-MM-DD-*.md`).

### 2b. Review Plan

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" --stage review_plan --plan-doc "PLAN_PATH"
```

### 2c. Iterate Plan

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" --stage iterate_plan --plan-doc "PLAN_PATH"
```

**Between each step:** If output contains questions, answer them and re-run that step.

## Stage 3: Execute

### 3a. Implement

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" --stage implement --plan-doc "PLAN_PATH"
```

Look for files changed and any errors.

### 3b. Commit

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" --stage commit
```

## Progress Reporting

After each step, report progress:

```markdown
=== Workflow Progress ===
Objective: {objective}

[✓] Research - {research_doc}
[✓] Create Plan - {plan_doc}
[✓] Review Plan
[✓] Iterate Plan
[→] Implement - in progress...
[ ] Commit
=========================
```

## Error Handling

- If a step fails (exit code 1), report the error and ask user how to proceed
- If output contains clarifying questions, answer the question and re-run that step
- Keyboard interrupt (exit code 130) means user cancelled

## Logs

Logs written to `.π/logs/workflow-*.log` (7-day retention).

## Options Reference

| Option | Description |
|--------|-------------|
| `--stage` | `research`, `create_plan`, `review_plan`, `iterate_plan`, `implement`, `commit` |
| `--research-doc PATH` | Path to research document |
| `--plan-doc PATH` | Path to plan document |
| `-v` | Verbose logging to console |
