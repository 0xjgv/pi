---
name: workflow
description: Orchestrate autonomous research → design → execute workflows. Use when given a development task that requires understanding the codebase, planning, and implementing changes.
---

# Autonomous Development Workflow

Run a multi-stage workflow using isolated SDK sessions. Each stage runs in its own context, keeping your main context clean.

```
Research → Design → [Review → Iterate]* → Execute → Commit
```

## Session Resumption

Each stage outputs a `SESSION_ID` that can be used to resume the conversation if needed (e.g., to provide corrections or additional context). Extract and store the session ID from each stage's output.

**Format**: `SESSION_ID: <id>` appears at the end of output after `---` separator.

## Stage 1: Research

```bash
python .claude/skills/workflow/scripts/stage_1_research_codebase.py "OBJECTIVE"
```

Read the output. Look for:

- The research document path (e.g., `thoughts/shared/research/YYYY-MM-DD-*.md`)
- `SESSION_ID: <id>` at end of output
- Whether implementation is needed

If no implementation needed, stop and report findings.

**To resume** (e.g., if research needs refinement):
```bash
python .claude/skills/workflow/scripts/stage_1_research_codebase.py "additional context" --session-id "ID"
```

## Stage 2: Design

```bash
python .claude/skills/workflow/scripts/stage_2_create_plan.py "OBJECTIVE" --research-doc "PATH"
```

Read the output. Look for:

- The plan document path (e.g., `thoughts/shared/plans/YYYY-MM-DD-*.md`)
- `SESSION_ID: <id>` at end of output

**To resume**:
```bash
python .claude/skills/workflow/scripts/stage_2_create_plan.py "refinements" --research-doc "PATH" --session-id "ID"
```

## Stage 3: Review Plan

```bash
python .claude/skills/workflow/scripts/stage_3_review_plan.py --plan-doc "PATH"
```

Read the output. Look for:

- Review findings (blocking, high-priority, optional)
- `SESSION_ID: <id>` at end of output

Use after design to validate plan completeness before implementation.

**To resume**:
```bash
python .claude/skills/workflow/scripts/stage_3_review_plan.py --plan-doc "PATH" --session-id "ID"
```

## Stage 4: Iterate Plan

```bash
python .claude/skills/workflow/scripts/stage_4_iterate_plan.py --plan-doc "PATH" --feedback "changes needed"
```

Read the output. Look for:

- Updated plan confirmation
- `SESSION_ID: <id>` at end of output

Use when plan needs refinement based on review findings or new requirements.

**To resume**:
```bash
python .claude/skills/workflow/scripts/stage_4_iterate_plan.py --plan-doc "PATH" --session-id "ID"
```

## Stage 5: Implement

```bash
python .claude/skills/workflow/scripts/stage_5_implement_plan.py "OBJECTIVE" --plan-doc "PATH"
```

Read the output. Look for:

- Files changed
- Commit hash (if committed)
- `SESSION_ID: <id>` at end of output

**To resume**:
```bash
python .claude/skills/workflow/scripts/stage_5_implement_plan.py "fix this" --plan-doc "PATH" --session-id "ID"
```

## Stage 6: Commit

```bash
python .claude/skills/workflow/scripts/stage_6_commit.py
```

Or with a commit message hint:
```bash
python .claude/skills/workflow/scripts/stage_6_commit.py "add feature X"
```

Read the output. Look for:

- Commit hash
- Files committed
- `SESSION_ID: <id>` at end of output

Use after implementation to finalize changes.

**To resume**:
```bash
python .claude/skills/workflow/scripts/stage_6_commit.py --session-id "ID"
```

## Progress Reporting

After each stage:

```markdown
=== Workflow Progress ===
Objective: {objective}

[✓] Stage 1: Research - {research_doc}
    Session: {research_session_id}
[✓] Stage 2: Design - {plan_doc}
    Session: {design_session_id}
[✓] Stage 3: Review - findings addressed
    Session: {review_session_id}
[✓] Stage 4: Iterate - plan refined
    Session: {iterate_session_id}
[✓] Stage 5: Implement - {files_changed} files
    Session: {implement_session_id}
[→] Stage 6: Commit - in progress...
=========================
```

## Error Handling

Scripts include validation and error handling:

- `--help` flag shows usage
- Invalid paths are rejected before execution
- Errors are reported to stderr with exit code 1
- Keyboard interrupt exits cleanly with code 130

If a script fails, you can resume the session with `--session-id` to continue from where it left off.

## Limitations

This skill provides simplified workflow orchestration for Claude Code sessions.
For production use with full features, use the π CLI directly:

| Feature | Skill | π CLI |
|---------|-------|-------|
| Safety hooks | ✓ | ✓ |
| Retry logic | ✗ | ✓ |
| Checkpoints | ✗ | ✓ |
| AITL | ✗ | ✓ |
| Memory | ✗ | ✓ |
| Session continuity | ✓ | ✓ |
