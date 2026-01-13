---
name: workflow
description: Orchestrate autonomous research → design → execute workflows. Use when given a development task that requires understanding the codebase, planning, and implementing changes.
---

# Autonomous Development Workflow

Run a 3-stage workflow using isolated SDK sessions. Each stage runs in its own context, keeping your main context clean.

## Stage 1: Research

```bash
python .claude/skills/workflow/scripts/stage_research.py "OBJECTIVE"
```

Read the output. Look for:

- The research document path (e.g., `thoughts/shared/research/YYYY-MM-DD-*.md`)
- Whether implementation is needed

If no implementation needed, stop and report findings.

## Stage 2: Design

```bash
python .claude/skills/workflow/scripts/stage_design.py "OBJECTIVE" --research-doc "RESEARCH_PATH"
```

Read the output. Look for:

- The plan document path (e.g., `thoughts/shared/plans/YYYY-MM-DD-*.md`)

## Stage 3: Execute

```bash
python .claude/skills/workflow/scripts/stage_execute.py "OBJECTIVE" --plan-doc "PLAN_PATH"
```

Read the output. Look for:

- Files changed
- Commit hash (if committed)

## Progress Reporting

After each stage:

```markdown
=== Workflow Progress ===
Objective: {objective}

[✓] Stage 1: Research - {research_doc}
[✓] Stage 2: Design - {plan_doc}
[→] Stage 3: Execute - in progress...
=========================
```

## Error Handling

If a script fails, report the error and ask the user how to proceed.
