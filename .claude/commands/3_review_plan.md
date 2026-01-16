---
description: Review existing implementation plans for completeness and accuracy
model: opus
---
# Review Implementation Plan

You are tasked with reviewing existing implementation plans for completeness and accuracy through systematic verification. You should be skeptical, thorough, and ensure changes are grounded in actual codebase reality.

## Purpose and Scope

**What this command does**:

- Performs systematic verification against a comprehensive checklist
- Identifies gaps, inconsistencies, and areas requiring validation through codebase research
- Categorizes findings by priority (blocking, high, optional, clarification needed)
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
/3_review_plan thoughts/shared/plans/2025-10-XX-feature-name.md
```

**Workflow**: Read → Verify → Research → Confirm → Update → Sync

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

### Step 2: Perform Verification Checklist

1. **Go through the verification checklist systematically**:

   Evaluate the plan against each verification criterion (in order of priority):

   **1. Libraries and Tools Verification**:
   - Check if libraries mentioned have specific versions
   - Verify tools are not deprecated or have known issues
   - Identify any missing dependency specifications

   **2. Codebase Alignment Verification**:
   - Verify the plan references actual files and components in the codebase
   - Check if the proposed approach matches existing patterns
   - Identify any conflicts with current architecture

   **3. Assumptions and Dependencies Verification**:
   - Review all stated assumptions for validity
   - Check if dependencies are properly documented
   - Identify any missing or unclear dependencies

   **4. Risks and Mitigations Verification**:
   - Verify risks are realistic and relevant
   - Check if mitigations are actionable
   - Identify any missing risk considerations

   **5. Scope and Alignment Verification**:
   - Verify "What We're NOT Doing" section is complete
   - Check if scope is clearly defined
   - Identify any scope creep or ambiguity

   **6. Completeness and Accuracy Verification**:
   - Check if all phases have clear steps
   - Verify success criteria are measurable
   - Check if file:line references are specific
   - Identify any vague or unclear sections

2. **Document findings as feedback items**:

   For each issue found, create a feedback item in the format:

   ```markdown
   - [ ] [section/component/file:line] Feedback comment
   ```

   **Categorize each item by priority**:
   - **Blocking**: Issues that prevent implementation or violate critical constraints
   - **High**: Important gaps or inaccuracies that should be addressed
   - **Optional**: Suggestions for improvement
   - **Clarification Needed**: Items requiring more context

3. **Organize findings by plan section**:
   - Group feedback by the plan sections they affect (assumptions, phases, success criteria, etc.)
   - This makes it easier to apply updates systematically

### Step 3: Research Gaps Identified During Verification

**Only spawn research tasks if verification findings require validation or additional technical understanding.**

If verification surfaced questions about code patterns, dependencies, or technical feasibility:

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

   **For external validation (use conditionally):**
   - **web-search-researcher** - To validate libraries, tools, and external dependencies

   **When to use web-search-researcher**:
   - Plan mentions specific library versions (check if deprecated/vulnerable)
   - Questions about external APIs or third-party services
   - Security concerns about dependencies
   - Unfamiliar technologies that need validation
   - Verifying best practices for specific tools

   **When NOT to use web-search-researcher**:
   - Internal architecture decisions
   - Codebase-specific patterns
   - Every review (adds latency)
   - Questions answerable from codebase alone

   **Be EXTREMELY specific about directories**:
   - Include full path context in prompts

3. **Read any new files identified by research**:
   - Read them FULLY into the main context
   - Cross-reference with the verification findings

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

1. **Present the changes made**:

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

2. **Be ready to iterate further** if user has follow-up concerns

## Important Guidelines

1. **Verify First, Act Second**:
   - Always complete the verification checklist before making changes
   - Let verification findings guide what needs fixing
   - Don't assume what's wrong - systematically check each criterion
   - Research to validate findings, not to guess at solutions

2. **Be Skeptical**:
   - Don't create findings without evidence
   - If something seems unclear, research to verify
   - Question vague sections in the plan - ask user for clarification
   - Verify technical feasibility with code research before flagging issues
   - Distinguish between actual problems and alternative approaches

3. **Be Surgical**:
   - Make precise edits, not wholesale rewrites
   - Preserve good content that doesn't need changing
   - Only research what's necessary to address verification findings
   - Don't over-engineer the updates

4. **Be Thorough**:
   - Read the entire existing plan before verification
   - Go through each verification criterion systematically
   - Address all blocking and high-priority findings
   - Research code patterns to validate verification concerns
   - Ensure updated sections maintain quality standards
   - Verify success criteria are measurable after updates

5. **Be Interactive**:
   - Present verification findings before making changes
   - Show what you plan to change and why
   - Allow user to prioritize or deprioritize findings
   - Communicate progress during research phases

6. **Track Progress**:
   - Use TodoWrite to track research tasks if complex
   - Update todos as you complete each finding
   - Mark tasks complete when addressed

7. **No Open Questions**:
   - If a verification finding is unclear, research or ask for clarification
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
User: /2.5_review_plan thoughts/plans/2025-10-16-feature.md
Assistant: [Reads plan, performs verification checklist]
Assistant: Verification complete. Found 3 blocking issues, 5 high-priority items...
[Presents organized findings]
User: Yes, please fix all blocking and high-priority issues
Assistant: [Makes targeted edits, syncs, presents results]
```

### Scenario 2: Review with research needed

```markdown
User: /2.5_review_plan thoughts/plans/2025-10-17-api-changes.md
Assistant: [Reads plan, performs verification]
Assistant: Verification identified that the authentication flow references may not match current implementation.
Let me research the actual auth patterns...
Assistant: [Spawns codebase-analyzer for auth directory]
Assistant: [Presents findings with validated information]
User: Good catch, proceed with updates
Assistant: [Updates plan with accurate technical details]
```

### Scenario 3: User has specific concerns

```markdown
User: /2.5_review_plan thoughts/plans/2025-10-18-db-migration.md - I'm worried about the success criteria
Assistant: [Reads plan, performs verification with focus on success criteria]
Assistant: Verification complete. Success criteria are indeed unmeasurable.
Additionally found assumptions about database version that may be outdated...
[Shows prioritized findings]
User: Fix the success criteria and verify the DB version assumption
Assistant: [Researches DB version, updates plan systematically]
```

### Scenario 4: Review with external validation needed

```markdown
User: /2.5_review_plan thoughts/plans/2025-10-20-upgrade-dependencies.md
Assistant: [Reads plan, performs verification]
Assistant: Verification found the plan mentions upgrading to React 18.2.0 and Express 4.x.
Let me research if these versions are current and check for any security advisories...
Assistant: [Spawns web-search-researcher for React and Express versions]
Assistant: Research found:
- React 18.2.0 is current but 18.3.1 is available with bug fixes
- Express 4.x has a security advisory - should specify 4.19.2+

I'll update the plan with these findings.
User: Good catch, proceed
Assistant: [Updates plan with correct versions and security notes]
```

### Scenario 5: Plan is already high quality

```markdown
User: /2.5_review_plan thoughts/plans/2025-10-19-refactor.md
Assistant: [Reads plan, performs verification]
Assistant: Great news! Verification found only minor optional improvements:
- Optional: Consider adding performance benchmarks to success criteria
- Optional: Link to similar past refactors in thoughts/

The plan is solid and ready for implementation. Would you like me to add those optional items?
User: No, let's proceed as-is
Assistant: Plan approved. Ready for implementation!
```

## Troubleshooting

### Issue: Verification finds no issues in a clearly incomplete plan

**Solution**:

- Review the verification checklist more carefully
- Check each section of the plan systematically
- Don't rush through the verification process
- Ask user if they have specific concerns to investigate

### Issue: Too many findings make it hard to prioritize

**Solution**:

- Focus on blocking and high-priority items first
- Ask user which areas they care about most
- Consider addressing optional items in a follow-up review
- Document deferred items in plan's "Future Improvements" section

### Issue: Research tasks return irrelevant results

**Solution**:

- Be more specific about directory paths in research prompts
- Use multiple focused queries instead of one broad query
- Request file:line references explicitly
- Spawn follow-up clarification tasks

### Issue: Uncertain whether something is actually an issue

**Solution**:

- Research the codebase to verify
- Mark as "Clarification Needed" if still uncertain
- Ask user for their perspective
- Escalate ambiguous findings rather than making assumptions

## Related Commands

- **`2_create_plan.md`**: Create new implementation plans from scratch
- **`4_implement_plan.md`**: Execute the implementation of a reviewed plan
- **`5_validate_plan.md`**: Validate plan assumptions against codebase

## References

- **Research Agents**:
  - Code: `codebase-locator`, `codebase-analyzer`, `codebase-pattern-finder`
  - Historical: `thoughts-locator`, `thoughts-analyzer`
  - External: `web-search-researcher` (conditional use)
- **Plan Template**: Check existing plans in `thoughts/shared/plans/` for structure
