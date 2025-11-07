"""
Analyzes review feedback to understand quality issues and improvement patterns.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class ReviewFeedback:
    """Structured review feedback analysis."""

    total_points: int = 0
    categories: Dict[str, int] = field(default_factory=lambda: {
        'completeness': 0,
        'correctness': 0,
        'testability': 0,
        'clarity': 0,
        'other': 0
    })
    severity: Dict[str, int] = field(default_factory=lambda: {
        'critical': 0,
        'major': 0,
        'minor': 0,
        'suggestion': 0
    })
    feedback_items: List[Dict[str, str]] = field(default_factory=list)

    @property
    def avg_severity(self) -> str:
        """Calculate average severity level."""
        if not self.total_points:
            return "none"

        weighted = (
            self.severity['critical'] * 4 +
            self.severity['major'] * 3 +
            self.severity['minor'] * 2 +
            self.severity['suggestion'] * 1
        )
        avg = weighted / self.total_points

        if avg >= 3.5:
            return "critical"
        elif avg >= 2.5:
            return "major"
        elif avg >= 1.5:
            return "minor"
        else:
            return "suggestion"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_points': self.total_points,
            'categories': self.categories,
            'severity': self.severity,
            'avg_severity': self.avg_severity,
            'feedback_items': self.feedback_items
        }


class ReviewAnalyzer:
    """Analyzes review documents to extract structured feedback."""

    # Keywords to categorize feedback
    CATEGORY_KEYWORDS = {
        'completeness': [
            'missing', 'incomplete', 'omitted', 'forgot', 'not included',
            'should include', 'needs to cover', 'add', 'specify'
        ],
        'correctness': [
            'incorrect', 'wrong', 'error', 'mistake', 'invalid',
            'doesn\'t work', 'won\'t solve', 'logical issue'
        ],
        'testability': [
            'test', 'verify', 'validate', 'measurable', 'success criteria',
            'how to confirm', 'acceptance'
        ],
        'clarity': [
            'unclear', 'ambiguous', 'vague', 'confusing', 'explain',
            'more detail', 'specify', 'clarify', 'what does this mean'
        ]
    }

    SEVERITY_KEYWORDS = {
        'critical': [
            'critical', 'must', 'required', 'essential', 'won\'t work',
            'blocking', 'breaks', 'fails'
        ],
        'major': [
            'should', 'important', 'significant', 'major issue',
            'problematic', 'needs attention'
        ],
        'minor': [
            'minor', 'small issue', 'could', 'consider', 'might want to'
        ],
        'suggestion': [
            'suggest', 'recommend', 'nice to have', 'optional',
            'could also', 'alternatively'
        ]
    }

    def __init__(self):
        pass

    def analyze_review(self, review_path: Path) -> ReviewFeedback:
        """
        Analyze a review document and extract structured feedback.

        Expects review in markdown format with bullet points or numbered lists.
        """
        with open(review_path) as f:
            review_content = f.read()

        feedback = ReviewFeedback()

        # Extract individual feedback points
        feedback_points = self._extract_feedback_points(review_content)
        feedback.total_points = len(feedback_points)

        for point in feedback_points:
            item = {
                'text': point,
                'category': self._categorize_feedback(point),
                'severity': self._assess_severity(point)
            }

            feedback.feedback_items.append(item)
            feedback.categories[item['category']] += 1
            feedback.severity[item['severity']] += 1

        return feedback

    def _extract_feedback_points(self, review: str) -> List[str]:
        """Extract individual feedback points from review text."""
        # Match bullet points (-, *, +) or numbered lists (1., 2.)
        patterns = [
            r'^[\-\*\+]\s+(.+)$',  # Bullet points
            r'^\d+\.\s+(.+)$',  # Numbered lists
            r'^[\-\*\+]\s+\*\*[\w\s]+\*\*[:\s]+(.+)$'  # Formatted bullets
        ]

        points = []
        for line in review.split('\n'):
            line = line.strip()
            for pattern in patterns:
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    points.append(match.group(1).strip())
                    break

        return points

    def _categorize_feedback(self, feedback: str) -> str:
        """Categorize a feedback point."""
        feedback_lower = feedback.lower()

        # Count keyword matches for each category
        scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in feedback_lower)
            scores[category] = score

        # Return category with highest score, or 'other' if all zero
        max_category = max(scores, key=scores.get)
        return max_category if scores[max_category] > 0 else 'other'

    def _assess_severity(self, feedback: str) -> str:
        """Assess severity level of a feedback point."""
        feedback_lower = feedback.lower()

        # Check keywords in order of severity
        for severity in ['critical', 'major', 'minor', 'suggestion']:
            keywords = self.SEVERITY_KEYWORDS[severity]
            if any(keyword in feedback_lower for keyword in keywords):
                return severity

        # Default to minor if no keywords match
        return 'minor'

    def compare_reviews(self, plan_review: ReviewFeedback, iterated_review: ReviewFeedback) -> Dict[str, Any]:
        """
        Compare reviews of initial plan vs iterated plan to measure improvement.

        Returns improvement metrics.
        """
        improvement = {
            'feedback_reduction': plan_review.total_points - iterated_review.total_points,
            'feedback_reduction_pct': (
                (plan_review.total_points - iterated_review.total_points) / plan_review.total_points * 100
                if plan_review.total_points > 0 else 0
            ),
            'severity_improvement': self._calculate_severity_improvement(plan_review, iterated_review),
            'category_improvement': self._calculate_category_improvement(plan_review, iterated_review),
            'remaining_issues': iterated_review.total_points,
            'effectiveness': 'high' if iterated_review.total_points <= plan_review.total_points * 0.3 else
                           'medium' if iterated_review.total_points <= plan_review.total_points * 0.6 else
                           'low'
        }

        return improvement

    def _calculate_severity_improvement(self, before: ReviewFeedback, after: ReviewFeedback) -> Dict[str, int]:
        """Calculate improvement in severity distribution."""
        improvement = {}
        for severity in ['critical', 'major', 'minor', 'suggestion']:
            improvement[severity] = before.severity[severity] - after.severity[severity]
        return improvement

    def _calculate_category_improvement(self, before: ReviewFeedback, after: ReviewFeedback) -> Dict[str, int]:
        """Calculate improvement in category distribution."""
        improvement = {}
        for category in before.categories:
            improvement[category] = before.categories[category] - after.categories[category]
        return improvement

    def generate_report(self, feedback: ReviewFeedback, title: str = "Review Analysis") -> str:
        """Generate human-readable review analysis report."""
        report = []
        report.append(f"# {title}\n")
        report.append(f"**Total Feedback Points**: {feedback.total_points}")
        report.append(f"**Average Severity**: {feedback.avg_severity}\n")

        report.append("## Feedback by Category\n")
        for category, count in sorted(feedback.categories.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                pct = (count / feedback.total_points * 100) if feedback.total_points > 0 else 0
                report.append(f"- **{category.title()}**: {count} ({pct:.1f}%)")

        report.append("\n## Feedback by Severity\n")
        for severity, count in sorted(feedback.severity.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                pct = (count / feedback.total_points * 100) if feedback.total_points > 0 else 0
                report.append(f"- **{severity.title()}**: {count} ({pct:.1f}%)")

        report.append("\n## Detailed Feedback Items\n")
        # Group by category
        by_category = {}
        for item in feedback.feedback_items:
            cat = item['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)

        for category, items in sorted(by_category.items()):
            report.append(f"\n### {category.title()}")
            for item in items:
                report.append(f"- [{item['severity'].upper()}] {item['text']}")

        return "\n".join(report)

    def generate_improvement_report(self, improvement: Dict[str, Any]) -> str:
        """Generate report comparing plan vs iterated plan."""
        report = []
        report.append("# Plan Iteration Effectiveness\n")
        report.append(f"**Feedback Reduction**: {improvement['feedback_reduction']} points ({improvement['feedback_reduction_pct']:.1f}%)")
        report.append(f"**Remaining Issues**: {improvement['remaining_issues']}")
        report.append(f"**Effectiveness Rating**: {improvement['effectiveness'].upper()}\n")

        report.append("## Severity Improvement\n")
        for severity, change in improvement['severity_improvement'].items():
            if change != 0:
                direction = "✓" if change > 0 else "✗"
                report.append(f"- {direction} **{severity.title()}**: {abs(change)} {'fewer' if change > 0 else 'more'}")

        report.append("\n## Category Improvement\n")
        for category, change in improvement['category_improvement'].items():
            if change != 0:
                direction = "✓" if change > 0 else "✗"
                report.append(f"- {direction} **{category.title()}**: {abs(change)} {'fewer' if change > 0 else 'more'}")

        return "\n".join(report)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python review_analyzer.py <review_file> [iterated_review_file]")
        sys.exit(1)

    analyzer = ReviewAnalyzer()

    review_path = Path(sys.argv[1])
    feedback = analyzer.analyze_review(review_path)

    print(analyzer.generate_report(feedback))

    # Save JSON
    output_path = review_path.parent / "review_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(feedback.to_dict(), f, indent=2)

    print(f"\n\nAnalysis saved to: {output_path}")

    # If iterated review provided, compare
    if len(sys.argv) >= 3:
        iterated_path = Path(sys.argv[2])
        iterated_feedback = analyzer.analyze_review(iterated_path)

        improvement = analyzer.compare_reviews(feedback, iterated_feedback)

        print("\n" + "="*50)
        print(analyzer.generate_improvement_report(improvement))

        # Save comparison
        comparison_path = review_path.parent / "iteration_improvement.json"
        with open(comparison_path, 'w') as f:
            json.dump(improvement, f, indent=2)

        print(f"\nComparison saved to: {comparison_path}")
