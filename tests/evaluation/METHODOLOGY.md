# Testing Methodology for π CLI Evaluation

## Overview

This document describes the comprehensive testing methodology for evaluating the quality and effectiveness of the π CLI tool. The evaluation framework measures whether generated plans solve problems correctly and require minimal manual correction (< 20% target).

## Testing Philosophy

Our evaluation approach is based on these principles:

1. **Quality Over Speed** - We prioritize plan correctness and completeness over execution time
2. **Real-World Scenarios** - Test with actual development tasks, not synthetic examples
3. **Objective Metrics** - Use quantifiable measurements (scores, percentages, counts)
4. **Iterative Improvement** - Track how review and iteration improve plan quality
5. **Manual Validation** - Combine automated analysis with human judgment

## Success Criteria

A high-quality plan must:
- **Score ≥ 80/100** on the quality rubric
- **Require < 20% manual correction** when executed
- **Address all review feedback** in the iteration stage
- **Be executable by any developer** without additional context

## Evaluation Dimensions

### 1. Plan Quality Score (100 points)

Measures the intrinsic quality of generated plans across four dimensions:

#### Completeness (35 points)
- All affected files identified (10 pts)
- Changes described at appropriate detail level (10 pts)
- Dependencies and prerequisites listed (5 pts)
- Edge cases considered (5 pts)
- Rollback/revert strategy included (5 pts)

**Why it matters**: Incomplete plans lead to rework, missed dependencies, and failed implementations.

**How measured**: Automated analysis checks for file mentions, dependency keywords, edge case discussions, and rollback strategies. Compared against expected outcomes defined in scenario.

#### Correctness (30 points)
- Proposed changes solve the stated problem (15 pts)
- No logical errors or contradictions (10 pts)
- Approach aligns with codebase patterns (5 pts)

**Why it matters**: Incorrect plans waste time and may introduce bugs.

**How measured**: Keyword overlap analysis, contradiction detection, and pattern alignment checks. Requires manual validation for full accuracy.

#### Testability (20 points)
- Success criteria are measurable (10 pts)
- Testing strategy is concrete and executable (10 pts)

**Why it matters**: Untestable plans can't be verified, leading to uncertainty about completion.

**How measured**: Automated analysis looks for testable verbs (pass, fail, return, equal), specific test types (unit, integration), and concrete test descriptions.

#### Clarity (15 points)
- Implementation steps are unambiguous (10 pts)
- Technical terms used correctly (5 pts)

**Why it matters**: Ambiguous plans require clarification and slow down implementation.

**How measured**: Count of action verbs, numbered steps, structured phases, and technical term usage.

### 2. Review Effectiveness

Measures how well the review stage identifies issues and how effectively the iteration stage addresses them.

**Metrics tracked**:
- Total feedback points
- Feedback by category (completeness, correctness, testability, clarity)
- Feedback by severity (critical, major, minor, suggestion)
- Improvement from plan to iterated plan
- % of feedback addressed

**Why it matters**: If review provides little feedback, plans are already good OR review is ineffective. If iteration doesn't address feedback, the stage is not adding value.

**How measured**:
- Parse review documents for feedback points
- Categorize and assess severity using keyword analysis
- Compare plan scores before and after iteration
- Calculate feedback reduction rate

### 3. Manual Correction Rate

Measures what percentage of plan items require human modification before they can be executed.

**Formula**:
```
correction_rate = (items_added + items_removed + items_modified) / total_plan_items × 100
```

**Target**: < 20%

**Why it matters**: This is the ultimate measure of plan quality - can a developer execute it as-is, or does it need significant rework?

**How measured**:
- **Option A (Diff-based)**: Compare generated plan to manually corrected version using text diffing
- **Option B (Annotation-based)**: Developer fills out correction template as they modify the plan

## Test Scenarios

### Scenario Selection Criteria

Scenarios are chosen to represent:
- **Common tasks**: Bug fixes, new features, refactoring
- **Various complexity levels**: Simple, medium, complex
- **Different contexts**: Solo developer and team environments
- **Real challenges**: Security issues, breaking changes, migrations

### Scenario Structure

Each scenario includes:

```json
{
  "id": "unique_identifier",
  "type": "solo_developer | team",
  "category": "bug_fix | new_feature | refactoring | breaking_change",
  "difficulty": "low | medium | high",
  "description": "Brief description",
  "prompt": "The exact prompt given to π CLI",
  "expected_outcomes": {
    "files_modified": ["list", "of", "files"],
    "files_created": ["new", "files"],
    "key_changes": ["description", "of", "changes"],
    "success_criteria": ["testable", "criteria"],
    "testing_strategy": ["test", "approach"]
  },
  "quality_baseline": {
    "completeness": 35,
    "correctness": 30,
    "testability": 20,
    "clarity": 15
  }
}
```

### Current Scenarios

1. **Bug Fix: Hook Bypass** (Solo, Medium)
   - Tests security vulnerability identification
   - Requires comprehensive fix with test coverage

2. **New Feature: Dry Run Mode** (Solo, High)
   - Tests cross-cutting feature design
   - Requires changes across multiple modules

3. **Breaking Change: Workflow API** (Team, High)
   - Tests backward compatibility handling
   - Requires migration guide and documentation

## Evaluation Process

### Step 1: Scenario Execution

```bash
python tests/evaluation/run_evaluation.py --scenario 01_bug_fix_hook_bypass
```

The runner:
1. Executes `π "<prompt>"` with the scenario prompt
2. Captures all output and workflow artifacts
3. Identifies generated files (plan, review, iterated plan)
4. Extracts workflow ID for artifact location

### Step 2: Automated Analysis

The runner automatically:

1. **Plan Quality Analysis**
   - Parses generated plan
   - Scores against rubric
   - Generates quality report
   - Saves JSON metrics

2. **Review Feedback Analysis**
   - Extracts feedback points
   - Categorizes and assesses severity
   - Generates review analysis report

3. **Iteration Effectiveness**
   - Analyzes iterated plan quality
   - Calculates improvement delta
   - Compares before/after scores

4. **Correction Template Generation**
   - Creates annotation template
   - Lists all plan items for tracking

### Step 3: Manual Validation

Developer reviews the generated plan and:

1. **Validates correctness**
   - Would this plan actually solve the problem?
   - Are there logical errors?
   - Does it align with codebase patterns?

2. **Tracks corrections**
   - Fill out correction template OR
   - Create corrected plan for diffing
   - Document why each correction was needed

3. **Calculates correction rate**
   ```bash
   python tests/evaluation/correction_tracker.py diff \
     thoughts/<workflow_id>/iterate-*.md \
     corrected_plan.md
   ```

### Step 4: Results Aggregation

```bash
python tests/evaluation/run_evaluation.py
```

Runs all scenarios and generates:
- Per-scenario quality reports
- Aggregate summary statistics
- Comprehensive evaluation report
- Recommendations for improvement

## Interpreting Results

### Quality Score Ratings

| Score | Rating | Meaning |
|-------|--------|---------|
| 90-100 | Excellent | Production-ready, minimal corrections |
| 80-89 | Good | Minor adjustments needed, meets threshold |
| 70-79 | Acceptable | Moderate corrections required |
| 60-69 | Poor | Significant rework needed |
| < 60 | Failing | Plan unusable as-is |

### Correction Rate Thresholds

| Rate | Assessment |
|------|------------|
| < 10% | Excellent - Minimal corrections |
| 10-20% | Good - Meets target |
| 20-30% | Acceptable - Slightly above target |
| 30-50% | Poor - Significant corrections |
| > 50% | Failing - Major rework required |

### Review Effectiveness

**Good indicators**:
- Plan score improves by ≥ 10 points after iteration
- 70%+ of review feedback addressed
- Severity shifts from critical/major to minor/suggestion

**Warning signs**:
- Many critical issues in review (plan quality too low)
- Iteration doesn't improve score (stage not effective)
- Few review points but low quality score (review ineffective)

## Using Results for Improvement

### If Quality Scores Are Low

**Investigate**:
- Which dimension is weakest? (completeness, correctness, testability, clarity)
- Are certain scenario types consistently worse?
- Is the research stage gathering enough context?

**Actions**:
- Improve prompts for weak dimensions
- Add examples to prompt templates
- Increase research depth for specific scenario types

### If Correction Rates Are High

**Investigate**:
- What types of corrections are most common?
- Are corrections adding missing items or fixing errors?
- Do corrections cluster in specific areas?

**Actions**:
- Update plan generation prompts to emphasize missing elements
- Add validation steps to catch common errors
- Improve the iteration stage to be more thorough

### If Review Isn't Effective

**Investigate**:
- Is review finding real issues?
- Is iteration addressing the feedback?
- Are review points too vague to act on?

**Actions**:
- Improve review prompt to be more specific
- Add structured feedback format to review stage
- Ensure iteration stage references and addresses each point

## Continuous Improvement

### Adding New Scenarios

1. Identify real tasks that π struggles with
2. Create scenario definition with expected outcomes
3. Run evaluation to establish baseline
4. Use results to improve prompts/workflow
5. Re-run to verify improvement

### Evolving Metrics

As the tool improves, consider:
- Raising quality score threshold (80 → 85)
- Lowering correction rate target (20% → 15%)
- Adding domain-specific metrics
- Tracking time-to-completion

### Benchmark Against Alternatives

Periodically compare π against:
- Manual implementation (time, quality)
- Claude web UI with same prompt
- Other AI coding tools

Track whether π's unique value proposition (4-stage workflow, safety, traceability) provides measurable benefits.

## Limitations and Caveats

### Automated Scoring Limitations

- **Correctness is hard to automate** - Requires human judgment for full validation
- **Context matters** - Scoring doesn't account for codebase-specific patterns
- **Keyword-based analysis** - Can miss nuanced issues
- **Baseline dependency** - Accuracy depends on good expected outcomes

### Manual Correction Tracking Challenges

- **Subjective judgment** - What counts as a "correction" vs. "preference"?
- **Effort variance** - Some corrections are trivial, others major
- **Annotation overhead** - Filling templates takes time

### Scenario Coverage

- **Not exhaustive** - Can't test every possible task type
- **Codebase specific** - Results may vary with different codebases
- **Evolving tool** - Scenarios may need updates as π changes

## Best Practices

1. **Run baseline first** - Establish current performance before changes
2. **Test incrementally** - After prompt/workflow changes, re-run scenarios
3. **Document findings** - Note patterns, edge cases, and insights
4. **Iterate on scenarios** - Add new scenarios as you discover gaps
5. **Combine methods** - Use automated + manual validation
6. **Track trends** - Monitor metrics over time, not just point-in-time
7. **Share results** - Use reports to guide team discussions

## Quick Reference

```bash
# Run all scenarios
python tests/evaluation/run_evaluation.py

# Run specific scenario
python tests/evaluation/run_evaluation.py --scenario 01_bug_fix_hook_bypass

# Analyze plan quality
python tests/evaluation/plan_analyzer.py \
  scenarios/01_bug_fix_hook_bypass \
  thoughts/<workflow_id>/plan-*.md

# Analyze review feedback
python tests/evaluation/review_analyzer.py \
  thoughts/<workflow_id>/review-*.md

# Track corrections (from template)
python tests/evaluation/correction_tracker.py \
  annotations corrections.json

# Track corrections (from diff)
python tests/evaluation/correction_tracker.py \
  diff original_plan.md corrected_plan.md

# Create correction template
python tests/evaluation/correction_tracker.py \
  template plan.md corrections_template.json
```

## Next Steps

1. **Run initial evaluation** - Establish baseline metrics
2. **Review results** - Identify weakest areas
3. **Prioritize improvements** - Focus on biggest gaps
4. **Implement changes** - Update prompts, workflow, or code
5. **Re-evaluate** - Measure impact of changes
6. **Iterate** - Continuous improvement cycle
