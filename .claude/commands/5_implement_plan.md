---
description: Execute implementation plan, writing code changes
model: opus
---
# Implement Plan

You are tasked with executing an implementation plan by writing code changes. You should follow the plan precisely while adapting to any unexpected issues discovered during implementation.

## Purpose and Scope

**What this command does**:

- Executes the implementation steps outlined in an approved plan
- Writes code changes, creates new files, modifies existing files
- Runs tests and validation as specified in the plan
- Reports on implementation progress and any deviations from plan

**What this command does NOT do**:

- Create new plans (use `2_create_plan.md` for that)
- Review or modify plans (use `3_review_plan.md` or `4_iterate_plan.md`)
- Make architectural decisions not in the plan
- Skip validation steps

**When to use this command**:

- After a plan has been created and reviewed
- When ready to write code based on an approved plan
- As part of the orchestrator's execution pipeline

## Quick Reference

**Typical invocation**:

```bash
/5_implement_plan thoughts/shared/plans/2025-10-XX-feature-name.md
```

**Workflow**: Read Plan -> Execute Phases -> Run Validation -> Report Results

## Initial Response

When this command is invoked:

1. **Parse the input to identify**:
   - Plan file path (e.g., `thoughts/shared/plans/2025-10-16-feature.md`)
   - Any additional context or constraints

2. **Handle different input scenarios**:

   **If NO plan file provided**:

   ```markdown
   I'll help you implement an existing plan.

   Which plan would you like to implement? Please provide the path to the plan file (e.g., `thoughts/shared/plans/2025-10-16-feature.md`).

   Tip: You can list recent plans with `ls -lt thoughts/shared/plans/ | head`
   ```

   Wait for user input.

   **If plan file provided**:
   - Proceed immediately to Step 1

## Process Steps

### Step 1: Read and Validate Plan

1. **Read the plan file COMPLETELY**:
   - Use the Read tool WITHOUT limit/offset parameters
   - Understand all phases and their steps
   - Note the success criteria (automated and manual)
   - Identify any prerequisites or dependencies

2. **Validate plan is ready for implementation**:
   - Check that the plan has been reviewed (look for review/iteration notes)
   - Verify all phases have clear, actionable steps
   - Ensure file paths and references are specific

3. **Create implementation todo list**:
   - Use TodoWrite to track each phase and major step
   - This provides visibility into progress

### Step 2: Execute Implementation Phases

For each phase in the plan:

1. **Announce the phase**:
   ```markdown
   ## Phase N: [Phase Name]
   Starting implementation of [brief description]...
   ```

2. **Execute each step in order**:
   - Read relevant files before modifying
   - Use Edit tool for surgical changes to existing files
   - Use Write tool for new files
   - Follow existing code patterns and conventions

3. **Handle implementation challenges**:
   - If a step is unclear, check the plan's context section
   - If code patterns differ from plan assumptions, adapt while preserving intent
   - Document any deviations in your progress report

4. **Mark phase complete** in todo list when done

### Step 3: Run Validation

1. **Execute automated verification**:
   - Run all commands specified in plan's "Automated Verification" section
   - Typically: `make check`, `make test`, type checking, linting

2. **Report validation results**:
   ```markdown
   ### Validation Results

   **Automated Checks**:
   - `make check`: [PASS/FAIL] [details if failed]
   - `make test`: [PASS/FAIL] [details if failed]

   **Files Changed**:
   - [list of files created/modified]
   ```

3. **If validation fails**:
   - Analyze the failure
   - Make targeted fixes
   - Re-run validation
   - Document what was fixed

### Step 4: Report Implementation Results

Present a summary:

```markdown
## Implementation Complete

**Plan**: `thoughts/shared/plans/[filename].md`

### Summary
[Brief description of what was implemented]

### Files Changed
- `path/to/file1.py` - [description of changes]
- `path/to/file2.py` - [description of changes]
- `path/to/new_file.py` - [new file description]

### Validation Status
- Type checking: PASS
- Linting: PASS
- Tests: PASS (N tests)

### Deviations from Plan
- [Any adaptations made during implementation]
- [Reasons for deviations]

### Ready for Commit
The implementation is complete and validated. Ready for commit with message:
"[Suggested commit message based on changes]"
```

## Important Guidelines

1. **Follow the Plan**:
   - Execute steps in order unless dependencies require reordering
   - Don't add features not in the plan
   - Don't skip steps without documenting why

2. **Be Precise**:
   - Read files before editing
   - Make surgical changes
   - Preserve existing code style

3. **Validate Continuously**:
   - Run tests after significant changes
   - Fix issues immediately
   - Don't accumulate broken state

4. **Document Deviations**:
   - If plan assumptions were wrong, note what was different
   - If adaptations were needed, explain why
   - This feedback improves future plans

5. **Track Progress**:
   - Update TodoWrite as you complete phases
   - Provide progress updates for long implementations
   - Mark completion clearly

## Error Handling

**If tests fail after changes**:
1. Analyze the failure carefully
2. Check if it's related to your changes or pre-existing
3. Fix issues related to your implementation
4. If pre-existing, document and continue

**If plan step is impossible**:
1. Explain why the step can't be completed as written
2. Propose an alternative approach
3. Get confirmation before proceeding differently
4. Document the deviation

**If unexpected complexity is discovered**:
1. Complete what you can safely
2. Report the complexity discovered
3. Suggest plan updates if needed
4. Don't attempt risky changes without guidance

## Related Commands

- **`2_create_plan.md`**: Create new implementation plans
- **`3_review_plan.md`**: Review plans before implementation
- **`4_iterate_plan.md`**: Update plans based on feedback
- **`6_create_commit.md`**: Commit implementation changes
