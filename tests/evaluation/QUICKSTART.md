# Quick Start Guide: Evaluating π CLI

## TL;DR

```bash
# 1. Run evaluation
cd /home/user/pi
python tests/evaluation/run_evaluation.py

# 2. Check results
cat tests/evaluation/results/<run_id>/REPORT.md

# 3. Manually review generated plans and track corrections
python tests/evaluation/correction_tracker.py template \
  thoughts/<workflow_id>/iterate-*.md \
  corrections.json

# Edit corrections.json as you review the plan

# 4. Calculate correction rate
python tests/evaluation/correction_tracker.py annotations corrections.json
```

**Success = Average quality score ≥ 80/100 AND correction rate < 20%**

---

## What Gets Evaluated

The evaluation measures 3 key aspects of plan quality:

1. **Plan Quality Score (0-100)**
   - Completeness: Are all files, dependencies, edge cases covered?
   - Correctness: Does it solve the problem without errors?
   - Testability: Can success be verified?
   - Clarity: Are steps clear and actionable?

2. **Review Effectiveness**
   - How many issues does review find?
   - Does iteration improve the plan?
   - What severity are the issues?

3. **Manual Correction Rate**
   - What % of plan items need human modification?
   - Target: < 20%

---

## Running Your First Evaluation

### Step 1: Run a Single Scenario

```bash
cd /home/user/pi
python tests/evaluation/run_evaluation.py --scenario 01_bug_fix_hook_bypass
```

This will:
- Execute π with the scenario prompt
- Analyze plan quality
- Analyze review feedback
- Compare plan vs iterated plan
- Generate reports

**Output location**: `tests/evaluation/results/<timestamp>/01_bug_fix_hook_bypass/`

### Step 2: Review the Quality Report

```bash
cat tests/evaluation/results/<timestamp>/01_bug_fix_hook_bypass/quality_report.md
```

Look for:
- Overall score and rating
- Weakest dimension (completeness, correctness, testability, clarity)
- Specific recommendations

### Step 3: Review the Generated Plan

```bash
cat thoughts/<workflow_id>/iterate-*.md
```

Ask yourself:
- Would this plan actually solve the problem?
- Can I execute it without additional information?
- Are there logical errors or missing steps?
- What would I need to change?

### Step 4: Track Your Corrections

As you review the plan, track what you'd need to change:

```bash
# Create a template
python tests/evaluation/correction_tracker.py template \
  thoughts/<workflow_id>/iterate-*.md \
  corrections.json
```

Edit `corrections.json` to record your corrections:

```json
{
  "total_items": 15,
  "corrections": [
    {
      "type": "modify",
      "item_index": 3,
      "before": "Update the validation logic",
      "after": "Update the validation logic in hooks.py:validate_command() to check for flag variants",
      "reason": "Too vague - needed specific location and method"
    },
    {
      "type": "add",
      "item": "Add integration test for command blocking with flags",
      "reason": "Missing test coverage for the fix"
    },
    {
      "type": "remove",
      "item_index": 7,
      "reason": "Duplicate of item 5"
    }
  ]
}
```

Calculate correction rate:

```bash
python tests/evaluation/correction_tracker.py annotations corrections.json
```

**Result**: If correction rate < 20%, the plan meets the quality threshold! 🎉

---

## Running Full Evaluation Suite

To evaluate all scenarios:

```bash
python tests/evaluation/run_evaluation.py
```

This runs all scenarios in `tests/evaluation/scenarios/` and generates:
- Per-scenario reports
- Aggregate statistics
- Comprehensive evaluation report

**Results**: `tests/evaluation/results/<timestamp>/REPORT.md`

### Key Metrics in Summary Report

```markdown
## Executive Summary

- Total Scenarios: 3
- Successful Runs: 3/3
- Average Quality Score: 82.3/100
- Scenarios Meeting Threshold (≥80): 2/3 (66.7%)
- Average Review Feedback Points: 4.7
- Average Quality Improvement (iteration): 8.3 points

## Overall Assessment

✓ PASS - π CLI generates high-quality plans consistently
```

---

## Understanding the Results

### Quality Score Interpretation

| Score | What It Means | Action |
|-------|---------------|--------|
| 90-100 | Excellent - Plans are production-ready | Keep doing what you're doing |
| 80-89 | Good - Minor improvements possible | Optional optimizations |
| 70-79 | Acceptable - Some gaps to address | Investigate weak dimensions |
| 60-69 | Poor - Needs work | Review prompts and workflow |
| < 60 | Failing - Serious issues | Major rework needed |

### Correction Rate Interpretation

| Rate | What It Means | Action |
|------|---------------|--------|
| < 10% | Excellent | Exceeding expectations |
| 10-20% | Good | Meeting target |
| 20-30% | Acceptable | Slightly above target, investigate |
| 30-50% | Poor | Prompts need improvement |
| > 50% | Failing | Plans not usable as-is |

### Review Effectiveness

**Good signs**:
- Quality improves by 10+ points after iteration
- Review finds 3-7 issues (not too few, not too many)
- Most feedback is minor/suggestions (not critical)

**Red flags**:
- No quality improvement after iteration
- 10+ critical issues in review
- Review finds nothing but quality score is low

---

## Adding Your Own Scenarios

1. Create a new directory in `tests/evaluation/scenarios/`:

```bash
mkdir tests/evaluation/scenarios/04_my_scenario
```

2. Create `scenario.json`:

```json
{
  "id": "04_my_scenario",
  "type": "solo_developer",
  "category": "bug_fix",
  "difficulty": "medium",
  "description": "Brief description of the task",
  "prompt": "The exact prompt you'd give to π",
  "expected_outcomes": {
    "files_modified": ["file1.py", "file2.py"],
    "key_changes": [
      "Change description 1",
      "Change description 2"
    ],
    "success_criteria": [
      "Tests pass",
      "Bug no longer reproduces"
    ],
    "testing_strategy": [
      "Add unit tests",
      "Manual verification"
    ]
  },
  "quality_baseline": {
    "completeness": 35,
    "correctness": 30,
    "testability": 20,
    "clarity": 15
  }
}
```

3. Run it:

```bash
python tests/evaluation/run_evaluation.py --scenario 04_my_scenario
```

---

## Common Workflows

### Baseline Evaluation

Before making changes to π:

```bash
# Run all scenarios
python tests/evaluation/run_evaluation.py

# Save the report
cp tests/evaluation/results/<timestamp>/REPORT.md baseline_report.md
```

### After Making Changes

After updating prompts or workflow:

```bash
# Run all scenarios again
python tests/evaluation/run_evaluation.py

# Compare results
diff baseline_report.md tests/evaluation/results/<new_timestamp>/REPORT.md
```

Look for:
- Did average quality score improve?
- Did correction rates decrease?
- Are there any regressions?

### Investigating Specific Issues

If plans consistently miss edge cases:

```bash
# Check completeness scores across scenarios
grep "edge_cases_considered" tests/evaluation/results/<timestamp>/*/quality_score.json

# Review what edge cases scenarios expected
grep "edge" tests/evaluation/scenarios/*/scenario.json
```

Update the plan generation prompt to emphasize edge case consideration.

### Tracking Progress Over Time

Create a tracking log:

```bash
# After each evaluation run
echo "$(date): Quality=${avg_score}, CorrectionRate=${avg_correction_rate}" >> evaluation_history.txt
```

---

## Troubleshooting

### "Could not find generated plan"

The evaluation runner looks for plan files in `thoughts/<workflow_id>/`.

**Fix**: Check that π actually created the workflow artifacts. Look in `.logs/` for workflow logs.

### Quality scores seem too high/low

Automated scoring has limitations, especially for correctness.

**Fix**: Always validate automated scores with manual review. Adjust scoring weights in `plan_analyzer.py` if needed.

### Correction rate tracking is tedious

Filling out correction templates takes time.

**Alternative**: Create a corrected version of the plan and use diff mode:

```bash
# Copy plan
cp thoughts/<workflow_id>/iterate-*.md corrected_plan.md

# Make your corrections
vim corrected_plan.md

# Calculate correction rate automatically
python tests/evaluation/correction_tracker.py diff \
  thoughts/<workflow_id>/iterate-*.md \
  corrected_plan.md
```

---

## Next Steps

1. **Run baseline evaluation** to establish current performance
2. **Review detailed reports** to identify weaknesses
3. **Prioritize improvements** based on impact
4. **Make changes** to prompts, workflow, or code
5. **Re-evaluate** to measure impact
6. **Iterate** for continuous improvement

For detailed methodology, see [METHODOLOGY.md](METHODOLOGY.md)

For framework documentation, see [README.md](README.md)

---

## Questions?

- **What's a good quality score?** ≥ 80/100
- **What's a good correction rate?** < 20%
- **How many scenarios should I have?** 5-10 covering common task types
- **How often should I evaluate?** After significant changes, or monthly
- **Can I automate this?** Yes - run evaluation in CI on prompt changes
