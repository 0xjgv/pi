---
description: Review existing implementation plans for completeness and accuracy
model: haiku
---

# Review Implementation Plan

You are tasked with reviewing existing implementation plans for completeness and accuracy using the review-plan skill. You should be skeptical, thorough, and ensure changes are grounded in actual codebase reality.

## Purpose and Scope

**What this command does**:

- Invokes the `review-plan` skill to get independent feedback from multiple AI reviewers
- Combines and prioritizes feedback from Codex and Claude reviewers
- Identifies gaps, inconsistencies, and areas requiring validation through codebase research
- Systematically addresses blocking and high-priority issues
- Updates plans with verified, actionable improvements

**What this command does NOT do**:

- Create new plans from scratch (use `2_create_plan.md` for that)
- Implement code changes (use `3_implement_plan.md` for that)
- Replace human judgment on plan approval
- Make arbitrary changes without reviewer guidance

**When to use this command**:

- Before starting implementation of a plan
- When a plan needs validation against current codebase state
- When stakeholders request a thorough review
- After significant architectural or requirement changes
- To ensure plan quality and completeness

## Quick Reference

**Typical invocation**:

```bash
/review_plan thoughts/plans/2025-10-XX-feature-name.md
```

**Workflow**: Read → Review → Research → Confirm → Update → Sync

## Initial Response

When this command is invoked:

1. **Parse the input to identify**:
   - Plan file path (e.g., `thoughts/plans/2025-10-16-feature.md`)
   - Any specific areas of concern the user wants reviewed

2. **Handle different input scenarios**:
   - If plan path provided: proceed with review
   - If no path provided: ask user to specify which plan to review
   - If user mentions specific concerns: note them for focused review

## Process Steps

### Step 1: Read and Understand Current Plan

1. **Read the existing plan file COMPLETELY**:
   - Use the Read tool WITHOUT limit/offset parameters
   - Understand the current structure, phases, and scope
   - Note the success criteria and implementation approach
   - Identify the plan's stated goals and constraints

### Step 2: Run Review Skill

1. **Invoke the review skill in parallel**:

   Use the `prompt-codex` and `prompt-claude` skills to run both reviewers simultaneously:

   ```bash
   # Codex reviewer (using prompt-codex skill)
   codex exec "Review the following technical plan for completeness and accuracy and provide feedback.
   Things to evaluate for (in order of priority):

   - Verify the libraries and tools used in the technical plan are up to date and not deprecated
   - Verify that the technical plan is aligned with the current codebase and product goals
   - Verify the assumptions and dependencies in the technical plan are valid
   - Verify the risks and mitigations in the technical plan are valid
   - Verify the alignment and scope in the technical plan is valid
   - Verify that the technical plan is complete and accurate
   
   Return a list of feedback items in the following format:
   - [ ] [section/component/file:line] Feedback comment 1
   - [ ] [section/component/file:line] Feedback comment 2
   - [ ] [section/component/file:line] Feedback comment 3
   
   Answer only with the list of feedback items.
   Plan to review: <absolute-path-to-plan.md>"

   # Claude reviewer (using prompt-claude skill)
   claude -p "Review the following technical plan for completeness and accuracy and provide feedback.
   Things to evaluate for (in order of priority):

   - Verify the libraries and tools used in the technical plan are up to date and not deprecated
   - Verify that the technical plan is aligned with the current codebase and product goals
   - Verify the assumptions and dependencies in the technical plan are valid
   - Verify the risks and mitigations in the technical plan are valid
   - Verify the alignment and scope in the technical plan is valid
   - Verify that the technical plan is complete and accurate
   
   Return a list of feedback items in the following format:
   - [ ] [section/component/file:line] Feedback comment 1
   - [ ] [section/component/file:line] Feedback comment 2
   - [ ] [section/component/file:line] Feedback comment 3
   
   Answer only with the list of feedback items.
   Plan to review: <absolute-path-to-plan.md>"
   ```

   **Key execution points**:
   - Use the `prompt-claude` skill (`skills/prompt-claude/SKILL.md`) for Claude review
   - Use the `prompt-codex` skill (`skills/prompt-codex/SKILL.md`) for Codex review
   - Use absolute paths to the plan file
   - Include the full plan content or path for context
   - Add any user-specified focus areas at the end of the prompt
   - Execute both commands in parallel for efficiency
   - If the agent requests additional information, submit an answer to the question based on what the plan overview and contents indicate.

2. **Wait for both reviewers to complete**:
   - Wait for both the `prompt-claude` and `prompt-codex` skills to complete (timeout of 2 minutes)
   - Ensure both reviewers have completed their reviews
   - Ensure both reviewers have provided their feedback

3. **Combine reviewer outputs**:
   - Merge the checklists from Codex and Claude into a single list, marking duplicates as IMPORTANT to review (a duplicate finding means that both reviewers found the same issue, making it more likely to be a valid issue).
   - Categorize each item by priority:
     - **Blocking**: Issues that prevent implementation or violate critical constraints
     - **High**: Important gaps or inaccuracies that should be addressed
     - **Optional**: Suggestions for improvement
     - **Clarification Needed**: Items requiring more context

4. **Organize findings by plan section**:
   - Group feedback by the plan sections they affect (assumptions, phases, success criteria, etc.)
   - This makes it easier to apply updates systematically

### Step 3: Research Gaps Identified by Reviewers

**Only spawn research tasks if reviewer findings require validation or additional technical understanding.**

If reviewers surfaced questions about code patterns, dependencies, or technical feasibility:

1. **Create a research todo list** using TodoWrite for tracking

2. **Spawn parallel sub-tasks for research**:
   Use the right agent for each type of research:

   **For code investigation:**
   - **codebase-locator** - To find relevant files
   - **codebase-analyzer** - To understand implementation details
   - **codebase-pattern-finder** - To find similar patterns

   **For historical context:**
   - **thoughts-locator** - To find related research or decisions
   - **thoughts-analyzer** - To extract insights from documents

   **Be EXTREMELY specific about directories**:
   - If the change involves "WUI", specify `humanlayer-wui/` directory
   - If it involves "daemon", specify `hld/` directory
   - Include full path context in prompts

3. **Read any new files identified by research**:
   - Read them FULLY into the main context
   - Cross-reference with the reviewer findings

4. **Wait for ALL sub-tasks to complete** before proceeding

### Step 4: Present Understanding and Confirm Next Steps

1. **Synthesize findings** into a clear summary

2. **Confirm next steps with the user** using the template below:

```markdown
## Review Complete

The review identified the following issues:

### Blocking Issues (must fix):
- [ ] [section/file:line] Issue description
- [ ] [section/file:line] Issue description

### High Priority (should fix):
- [ ] [section/file:line] Issue description
- [ ] [section/file:line] Issue description

### Optional Improvements:
- [ ] [section/file:line] Suggestion

### Items Requiring Clarification:
- [ ] [section/file:line] Question that needs your input

### Research Findings:
- [Key discovery from codebase that affects the plan]
- [Validated assumption or constraint]

I plan to update the plan to address all blocking and high-priority items. 
The changes will focus on: [brief summary of main updates].

Should I proceed with these updates?
```

1. **Get user confirmation** before proceeding to edits

### Step 5: Update the Plan

1. **Address reviewer findings systematically**:
   - Work through each blocking item first, then high-priority items
   - Document rationale for any issues you defer or mark as out-of-scope
   - For clarification items, either resolve with user input or document as open questions

2. **Make focused, precise edits** to the existing plan:
   - Use the Edit tool for surgical changes
   - Maintain the existing structure unless reviewer findings require restructuring
   - Keep all file:line references accurate
   - Update success criteria if reviewers found them unmeasurable or incomplete

3. **Ensure consistency across all updates**:
   - If adding a new phase, ensure it follows the existing pattern
   - If modifying scope, update "What We're NOT Doing" section
   - If changing approach, update "Implementation Approach" section
   - If updating dependencies, reflect them in "Assumptions & Dependencies"
   - Maintain the distinction between automated vs manual success criteria

4. **Preserve quality standards**:
   - Include specific file paths and line numbers for new content
   - Write measurable success criteria
   - Use `make` commands for automated verification
   - Keep language clear and actionable
   - Ensure technical accuracy based on research findings

### Step 6: Sync and Present Results

1. **Sync the updated plan**:
   - Run `humanlayer thoughts sync`
   - This ensures changes are properly indexed

2. **Present the changes made**:

   ```markdown
   ## Review Complete - Plan Updated

   I've updated the plan at `thoughts/plans/[filename].md`

   ### Issues Addressed:
   ✅ [Blocking issue 1] - Fixed by [specific change]
   ✅ [High priority issue 2] - Updated [section] to [improvement]
   ✅ [High priority issue 3] - Added [missing element]

   ### Issues Deferred:
   - [Optional item] - Reason for deferral

   ### Outstanding Questions:
   - [Clarification item] - Needs your input on [specific question]

   ### Key Improvements:
   - [Main improvement to plan quality/completeness]
   - [Another significant enhancement]

   The plan is now ready for implementation. Would you like me to review any specific section in more detail?
   ```

3. **Be ready to iterate further** if user has follow-up concerns

## Important Guidelines

1. **Review First, Act Second**:
   - Always run the review skill before making changes
   - Let reviewer feedback guide what needs fixing
   - Don't assume what's wrong - let the reviewers tell you
   - Research to validate findings, not to guess at solutions

2. **Be Skeptical**:
   - Don't blindly accept reviewer feedback without validation
   - If a finding seems wrong, research to verify
   - Question vague feedback - ask reviewers or user for clarification
   - Verify technical feasibility with code research before updating plan
   - Point out potential conflicts between reviewer suggestions

3. **Be Surgical**:
   - Make precise edits, not wholesale rewrites
   - Preserve good content that doesn't need changing
   - Only research what's necessary to address reviewer findings
   - Don't over-engineer the updates

4. **Be Thorough**:
   - Read the entire existing plan before running review
   - Address all blocking and high-priority findings
   - Research code patterns to validate reviewer concerns
   - Ensure updated sections maintain quality standards
   - Verify success criteria are measurable after updates

5. **Be Interactive**:
   - Present review findings before making changes
   - Show what you plan to change and why
   - Allow user to prioritize or deprioritize findings
   - Communicate progress during research phases

6. **Track Progress**:
   - Use TodoWrite to track research tasks if complex
   - Update todos as you complete each finding
   - Mark tasks complete when addressed

7. **No Open Questions**:
   - If a reviewer finding is unclear, ask for clarification
   - If research is inconclusive, escalate to user
   - Do NOT update the plan with unresolved questions
   - Every change must be complete and actionable
   - Document deferred items with clear rationale

## Success Criteria Guidelines

When updating success criteria, always maintain the two-category structure:

1. **Automated Verification** (can be run by execution agents):
   - Commands that can be run: `make test`, `npm run lint`, etc.
   - Specific files that should exist
   - Code compilation/type checking

2. **Manual Verification** (requires human testing):
   - UI/UX functionality
   - Performance under real conditions
   - Edge cases that are hard to automate
   - User acceptance criteria

## Sub-task Spawning Best Practices

When spawning research sub-tasks:

1. **Only spawn if truly needed** - don't research for simple changes
2. **Spawn multiple tasks in parallel** for efficiency
3. **Each task should be focused** on a specific area
4. **Provide detailed instructions** including:
   - Exactly what to search for
   - Which directories to focus on
   - What information to extract
   - Expected output format
5. **Request specific file:line references** in responses
6. **Wait for all tasks to complete** before synthesizing
7. **Verify sub-task results** - if something seems off, spawn follow-up tasks

## Example Interaction Flows

### Scenario 1: Standard review with findings

```markdown
User: /review_plan thoughts/plans/2025-10-16-feature.md
Assistant: [Reads plan, runs review skill with both codex and claude]
Assistant: Review complete. Found 3 blocking issues, 5 high-priority items...
[Presents organized findings]
User: Yes, please fix all blocking and high-priority issues
Assistant: [Makes targeted edits, syncs, presents results]
```

### Scenario 2: Review with research needed

```markdown
User: /review_plan thoughts/plans/2025-10-17-api-changes.md
Assistant: [Reads plan, runs review]
Assistant: Reviewers question whether the authentication flow matches current implementation.
Let me research the actual auth patterns...
Assistant: [Spawns codebase-analyzer for auth directory]
Assistant: [Presents findings with validated information]
User: Good catch, proceed with updates
Assistant: [Updates plan with accurate technical details]
```

### Scenario 3: User has specific concerns

```markdown
User: /review_plan thoughts/plans/2025-10-18-db-migration.md - I'm worried about the success criteria
Assistant: [Reads plan, runs review with focus on success criteria]
Assistant: Review complete. Reviewers also flagged the success criteria as unmeasurable.
Additionally found assumptions about database version that may be outdated...
[Shows prioritized findings]
User: Fix the success criteria and verify the DB version assumption
Assistant: [Researches DB version, updates plan systematically]
```

### Scenario 4: Plan is already high quality

```markdown
User: /review_plan thoughts/plans/2025-10-19-refactor.md
Assistant: [Reads plan, runs review]
Assistant: Great news! The review found only minor optional improvements:
- Optional: Consider adding performance benchmarks to success criteria
- Optional: Link to similar past refactors in thoughts/

The plan is solid and ready for implementation. Would you like me to add those optional items?
User: No, let's proceed as-is
Assistant: Plan approved. Ready for implementation!
```

## Troubleshooting

### Issue: Reviewers return empty or vague feedback

**Solution**:

- Ensure the plan file is readable and contains substantial content
- Verify the absolute path to the plan is correct
- Check that the plan follows expected structure (phases, success criteria, etc.)
- Try adding specific focus areas in the prompt: "Pay special attention to [section]"

### Issue: Duplicate feedback items flagged but not actually duplicates

**Solution**:

- This indicates conceptual similarity even if wording differs
- Treat as a signal that the issue is particularly important
- Investigate both perspectives to get complete understanding

### Issue: Research tasks return irrelevant results

**Solution**:

- Be more specific about directory paths in research prompts
- Use multiple focused queries instead of one broad query
- Request file:line references explicitly
- Spawn follow-up clarification tasks

### Issue: Conflicting feedback between reviewers

**Solution**:

- This is expected - different perspectives are valuable
- Research the codebase to determine which is correct
- Document both perspectives if both have merit
- Escalate to user if unresolvable

### Issue: Too many optional findings, hard to prioritize

**Solution**:

- Focus on blocking and high-priority items first
- Ask user which optional items they care about most
- Consider deferring optional items to a follow-up review
- Document deferred items in plan's "Future Improvements" section

## Related Commands

- **`2_create_plan.md`**: Create new implementation plans from scratch
- **`2.5_iterate_plan.md`**: Iterate on plans based on user-requested changes
- **`3_implement_plan.md`**: Execute the implementation of a reviewed plan
- **`5_validate_plan.md`**: Validate plan assumptions against codebase

## References

- **Research Agents**: `agents/codebase-*.md`, `agents/thoughts-*.md`, `agents/web-search-*.md`
- **Plan Template**: Check existing plans in `thoughts/plans/` for structure
