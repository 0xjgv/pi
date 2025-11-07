# CLI Evaluation Framework

## Objective
Measure plan quality and manual correction rate to ensure plans require < 20% manual correction.

## Success Criteria
- **Plan Quality Score**: ≥ 80/100 average across scenarios
- **Manual Correction Rate**: < 20% of plan items need modification
- **Review Effectiveness**: Feedback leads to measurable plan improvement

## Evaluation Dimensions

### 1. Plan Quality Metrics (100 points total)

#### Completeness (35 points)
- [ ] All affected files identified (10 pts)
- [ ] Changes described at appropriate detail level (10 pts)
- [ ] Dependencies and prerequisites listed (5 pts)
- [ ] Edge cases considered (5 pts)
- [ ] Rollback/revert strategy included (5 pts)

#### Correctness (30 points)
- [ ] Proposed changes solve the stated problem (15 pts)
- [ ] No logical errors or contradictions (10 pts)
- [ ] Approach aligns with codebase patterns (5 pts)

#### Testability (20 points)
- [ ] Success criteria are measurable (10 pts)
- [ ] Testing strategy is concrete and executable (10 pts)

#### Clarity (15 points)
- [ ] Implementation steps are unambiguous (10 pts)
- [ ] Technical terms used correctly (5 pts)

### 2. Manual Correction Rate

Calculated as:
```
correction_rate = (items_modified + items_removed) / total_plan_items
```

**Target**: < 20%

### 3. Review Effectiveness

Tracks:
- Number of feedback points per review
- % of feedback addressed in iteration
- Quality score improvement (plan → iterated plan)

## Test Scenarios

### Solo Developer Scenarios
1. Bug fix in existing feature
2. Add new CLI command
3. Refactor for better code organization
4. Performance optimization
5. Add error handling

### Team Scenarios
6. Multi-file feature spanning modules
7. Breaking API change with migration path
8. Integration with third-party service
9. Database schema migration
10. Deprecation and removal strategy

## Running Evaluations

```bash
# Run all scenarios
python tests/evaluation/run_evaluation.py

# Run specific scenario
python tests/evaluation/run_evaluation.py --scenario 01_bug_fix

# Analyze results
python tests/evaluation/analyze_results.py --workflow-id <id>
```

## Output

Each evaluation produces:
```
tests/evaluation/results/{run_id}/
├── summary.json              # Aggregate metrics
├── scenarios/
│   ├── 01_bug_fix/
│   │   ├── plan.md           # Generated plan
│   │   ├── review.md         # Review feedback
│   │   ├── iterated_plan.md  # Final plan
│   │   ├── scores.json       # Quality metrics
│   │   └── corrections.json  # Manual changes needed
│   └── ...
└── report.md                 # Human-readable report
```

## Quality Rubric

| Score Range | Rating | Interpretation |
|-------------|--------|----------------|
| 90-100 | Excellent | Production-ready, minimal corrections |
| 80-89 | Good | Minor adjustments needed |
| 70-79 | Acceptable | Moderate corrections required |
| 60-69 | Poor | Significant rework needed |
| < 60 | Failing | Plan unusable as-is |
