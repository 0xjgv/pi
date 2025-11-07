"""
Analyzes generated plans and scores them against quality metrics.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class PlanQualityScore:
    """Quality score breakdown for a plan."""

    # Completeness (35 points)
    all_files_identified: int = 0  # 10 pts
    changes_detailed: int = 0  # 10 pts
    dependencies_listed: int = 0  # 5 pts
    edge_cases_considered: int = 0  # 5 pts
    rollback_strategy: int = 0  # 5 pts

    # Correctness (30 points)
    solves_problem: int = 0  # 15 pts
    no_logical_errors: int = 0  # 10 pts
    aligns_with_patterns: int = 0  # 5 pts

    # Testability (20 points)
    measurable_criteria: int = 0  # 10 pts
    executable_strategy: int = 0  # 10 pts

    # Clarity (15 points)
    unambiguous_steps: int = 0  # 10 pts
    correct_terminology: int = 0  # 5 pts

    @property
    def completeness_total(self) -> int:
        return (
            self.all_files_identified +
            self.changes_detailed +
            self.dependencies_listed +
            self.edge_cases_considered +
            self.rollback_strategy
        )

    @property
    def correctness_total(self) -> int:
        return (
            self.solves_problem +
            self.no_logical_errors +
            self.aligns_with_patterns
        )

    @property
    def testability_total(self) -> int:
        return (
            self.measurable_criteria +
            self.executable_strategy
        )

    @property
    def clarity_total(self) -> int:
        return (
            self.unambiguous_steps +
            self.correct_terminology
        )

    @property
    def total_score(self) -> int:
        return (
            self.completeness_total +
            self.correctness_total +
            self.testability_total +
            self.clarity_total
        )

    @property
    def rating(self) -> str:
        score = self.total_score
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Acceptable"
        elif score >= 60:
            return "Poor"
        else:
            return "Failing"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['completeness_total'] = self.completeness_total
        d['correctness_total'] = self.correctness_total
        d['testability_total'] = self.testability_total
        d['clarity_total'] = self.clarity_total
        d['total_score'] = self.total_score
        d['rating'] = self.rating
        return d


class PlanAnalyzer:
    """Analyzes plan documents and assigns quality scores."""

    def __init__(self, scenario_path: Path):
        """Initialize with a scenario definition."""
        self.scenario_path = scenario_path
        with open(scenario_path / "scenario.json") as f:
            self.scenario = json.load(f)
        self.expected = self.scenario["expected_outcomes"]

    def analyze_plan(self, plan_path: Path) -> PlanQualityScore:
        """
        Analyze a plan document and return quality score.

        Uses both automated checks and comparison against expected outcomes.
        """
        with open(plan_path) as f:
            plan_content = f.read()

        score = PlanQualityScore()

        # Completeness checks
        score.all_files_identified = self._check_files_identified(plan_content)
        score.changes_detailed = self._check_changes_detail(plan_content)
        score.dependencies_listed = self._check_dependencies(plan_content)
        score.edge_cases_considered = self._check_edge_cases(plan_content)
        score.rollback_strategy = self._check_rollback(plan_content)

        # Correctness checks (requires manual review, provide partial automation)
        score.solves_problem = self._check_problem_solving(plan_content)
        score.no_logical_errors = self._check_logical_consistency(plan_content)
        score.aligns_with_patterns = self._check_pattern_alignment(plan_content)

        # Testability checks
        score.measurable_criteria = self._check_success_criteria(plan_content)
        score.executable_strategy = self._check_test_strategy(plan_content)

        # Clarity checks
        score.unambiguous_steps = self._check_step_clarity(plan_content)
        score.correct_terminology = self._check_terminology(plan_content)

        return score

    def _check_files_identified(self, plan: str) -> int:
        """Check if all expected files are mentioned in plan."""
        expected_files = set(
            self.expected.get("files_modified", []) +
            self.expected.get("files_created", [])
        )

        if not expected_files:
            return 10  # No specific files required

        mentioned_files = set(re.findall(r'[\w/]+\.py', plan))
        coverage = len(expected_files & mentioned_files) / len(expected_files)

        if coverage >= 1.0:
            return 10
        elif coverage >= 0.8:
            return 8
        elif coverage >= 0.6:
            return 6
        elif coverage >= 0.4:
            return 4
        else:
            return 2

    def _check_changes_detail(self, plan: str) -> int:
        """Check if changes are described at appropriate detail level."""
        # Look for structured change descriptions
        has_phases = bool(re.search(r'(?i)(phase|step)\s+\d', plan))
        has_file_sections = bool(re.search(r'(?i)file.*changes|changes.*file', plan))
        has_code_examples = plan.count('```') >= 2

        score = 0
        if has_phases:
            score += 4
        if has_file_sections:
            score += 3
        if has_code_examples:
            score += 3

        return min(score, 10)

    def _check_dependencies(self, plan: str) -> int:
        """Check if dependencies and prerequisites are listed."""
        dependency_indicators = [
            'prerequisite', 'dependency', 'depends on', 'requires',
            'must be done before', 'order of operations'
        ]

        mentions = sum(1 for indicator in dependency_indicators if indicator.lower() in plan.lower())

        if mentions >= 3:
            return 5
        elif mentions >= 2:
            return 4
        elif mentions >= 1:
            return 3
        else:
            return 0

    def _check_edge_cases(self, plan: str) -> int:
        """Check if edge cases are considered."""
        edge_case_indicators = [
            'edge case', 'corner case', 'error handling', 'failure mode',
            'what if', 'handle invalid', 'boundary condition'
        ]

        mentions = sum(1 for indicator in edge_case_indicators if indicator.lower() in plan.lower())

        if mentions >= 3:
            return 5
        elif mentions >= 2:
            return 4
        elif mentions >= 1:
            return 2
        else:
            return 0

    def _check_rollback(self, plan: str) -> int:
        """Check if rollback/revert strategy is included."""
        rollback_indicators = [
            'rollback', 'revert', 'undo', 'backward compatibility',
            'migration path', 'deprecation'
        ]

        mentions = sum(1 for indicator in rollback_indicators if indicator.lower() in plan.lower())

        if mentions >= 2:
            return 5
        elif mentions >= 1:
            return 3
        else:
            return 0

    def _check_problem_solving(self, plan: str) -> int:
        """Check if plan addresses the stated problem (requires manual review)."""
        # Automated: Check if plan mentions key aspects of the problem
        prompt_keywords = set(self.scenario['prompt'].lower().split())
        plan_keywords = set(plan.lower().split())

        keyword_overlap = len(prompt_keywords & plan_keywords) / len(prompt_keywords)

        if keyword_overlap >= 0.7:
            return 12  # High confidence
        elif keyword_overlap >= 0.5:
            return 10
        else:
            return 5  # Needs manual review

    def _check_logical_consistency(self, plan: str) -> int:
        """Check for logical contradictions (partial automation)."""
        # Simple contradiction detection
        contradictions = [
            ('add', 'remove'),
            ('create', 'delete'),
            ('increase', 'decrease')
        ]

        score = 10  # Start optimistic

        for word1, word2 in contradictions:
            if word1 in plan.lower() and word2 in plan.lower():
                # Check if they're in close proximity (potential contradiction)
                pattern = f'{word1}.*{word2}|{word2}.*{word1}'
                if re.search(pattern, plan.lower()):
                    score -= 2

        return max(score, 5)  # Minimum 5 points

    def _check_pattern_alignment(self, plan: str) -> int:
        """Check if approach aligns with codebase patterns (needs manual review)."""
        # Placeholder: Look for references to existing patterns
        pattern_indicators = [
            'similar to', 'following the pattern', 'consistent with',
            'like existing', 'matches the style'
        ]

        mentions = sum(1 for indicator in pattern_indicators if indicator.lower() in plan.lower())

        if mentions >= 2:
            return 5
        elif mentions >= 1:
            return 3
        else:
            return 2  # Neutral

    def _check_success_criteria(self, plan: str) -> int:
        """Check if success criteria are measurable."""
        # Look for success criteria section
        has_section = bool(re.search(r'(?i)success criteria|acceptance criteria', plan))

        if not has_section:
            return 2

        # Count testable criteria (should have verbs like "pass", "return", "equal")
        testable_verbs = [
            'pass', 'fail', 'return', 'equal', 'match', 'contain',
            'respond', 'execute', 'complete', 'verify'
        ]

        # Extract success criteria section
        criteria_match = re.search(
            r'(?i)(success|acceptance) criteria.*?(?=\n#|\Z)',
            plan,
            re.DOTALL
        )

        if criteria_match:
            criteria_text = criteria_match.group()
            testable_count = sum(1 for verb in testable_verbs if verb in criteria_text.lower())

            if testable_count >= 3:
                return 10
            elif testable_count >= 2:
                return 7
            else:
                return 5

        return 3

    def _check_test_strategy(self, plan: str) -> int:
        """Check if testing strategy is concrete and executable."""
        has_section = bool(re.search(r'(?i)test(ing)? (strategy|plan|approach)', plan))

        if not has_section:
            return 2

        # Look for specific test types
        test_types = [
            'unit test', 'integration test', 'e2e test', 'regression test',
            'test case', 'test file', 'pytest', 'assert'
        ]

        mentions = sum(1 for test_type in test_types if test_type.lower() in plan.lower())

        if mentions >= 4:
            return 10
        elif mentions >= 3:
            return 8
        elif mentions >= 2:
            return 6
        else:
            return 3

    def _check_step_clarity(self, plan: str) -> int:
        """Check if implementation steps are unambiguous."""
        # Look for numbered steps or clear phases
        numbered_steps = len(re.findall(r'^\d+\.', plan, re.MULTILINE))
        has_phases = bool(re.search(r'(?i)phase \d+', plan))

        # Look for action verbs (clear instructions)
        action_verbs = [
            'create', 'update', 'modify', 'add', 'remove', 'implement',
            'define', 'extract', 'refactor', 'test'
        ]

        verb_count = sum(1 for verb in action_verbs if f' {verb} ' in plan.lower())

        score = 0
        if numbered_steps >= 5 or has_phases:
            score += 5
        if verb_count >= 10:
            score += 5
        elif verb_count >= 5:
            score += 3

        return min(score, 10)

    def _check_terminology(self, plan: str) -> int:
        """Check if technical terms are used correctly (basic check)."""
        # Look for technical terms related to the domain
        # This is a basic check; manual review needed for accuracy

        technical_terms = [
            'function', 'class', 'method', 'module', 'API', 'hook',
            'async', 'await', 'import', 'export', 'CLI', 'workflow'
        ]

        term_usage = sum(1 for term in technical_terms if term.lower() in plan.lower())

        if term_usage >= 5:
            return 5
        elif term_usage >= 3:
            return 4
        else:
            return 3

    def generate_report(self, score: PlanQualityScore) -> str:
        """Generate a human-readable quality report."""
        report = []
        report.append("# Plan Quality Report\n")
        report.append(f"**Overall Score**: {score.total_score}/100 ({score.rating})\n")
        report.append("\n## Score Breakdown\n")

        report.append(f"### Completeness: {score.completeness_total}/35")
        report.append(f"- Files identified: {score.all_files_identified}/10")
        report.append(f"- Changes detailed: {score.changes_detailed}/10")
        report.append(f"- Dependencies listed: {score.dependencies_listed}/5")
        report.append(f"- Edge cases considered: {score.edge_cases_considered}/5")
        report.append(f"- Rollback strategy: {score.rollback_strategy}/5\n")

        report.append(f"### Correctness: {score.correctness_total}/30")
        report.append(f"- Solves problem: {score.solves_problem}/15")
        report.append(f"- No logical errors: {score.no_logical_errors}/10")
        report.append(f"- Aligns with patterns: {score.aligns_with_patterns}/5\n")

        report.append(f"### Testability: {score.testability_total}/20")
        report.append(f"- Measurable criteria: {score.measurable_criteria}/10")
        report.append(f"- Executable strategy: {score.executable_strategy}/10\n")

        report.append(f"### Clarity: {score.clarity_total}/15")
        report.append(f"- Unambiguous steps: {score.unambiguous_steps}/10")
        report.append(f"- Correct terminology: {score.correct_terminology}/5\n")

        # Add recommendations
        report.append("## Recommendations\n")
        if score.completeness_total < 28:
            report.append("- **Completeness**: Add more detail about files, dependencies, or edge cases")
        if score.correctness_total < 24:
            report.append("- **Correctness**: Review logical consistency and problem alignment")
        if score.testability_total < 16:
            report.append("- **Testability**: Strengthen success criteria and testing strategy")
        if score.clarity_total < 12:
            report.append("- **Clarity**: Make implementation steps more explicit and actionable")

        return "\n".join(report)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 3:
        print("Usage: python plan_analyzer.py <scenario_dir> <plan_file>")
        sys.exit(1)

    scenario_path = Path(sys.argv[1])
    plan_path = Path(sys.argv[2])

    analyzer = PlanAnalyzer(scenario_path)
    score = analyzer.analyze_plan(plan_path)

    print(analyzer.generate_report(score))

    # Save JSON
    output_path = plan_path.parent / "quality_score.json"
    with open(output_path, 'w') as f:
        json.dump(score.to_dict(), f, indent=2)

    print(f"\nScore saved to: {output_path}")
