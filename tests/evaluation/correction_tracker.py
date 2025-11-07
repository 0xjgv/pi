"""
Tracks manual corrections made to plans to calculate correction rate.

The goal is to measure what % of plan items require human modification.
Target: < 20% correction rate.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field
import difflib


@dataclass
class CorrectionMetrics:
    """Metrics for manual corrections to a plan."""

    total_items: int = 0
    items_added: int = 0
    items_removed: int = 0
    items_modified: int = 0
    items_unchanged: int = 0

    @property
    def correction_rate(self) -> float:
        """Calculate correction rate as % of items needing changes."""
        if self.total_items == 0:
            return 0.0
        return ((self.items_added + self.items_removed + self.items_modified) / self.total_items) * 100

    @property
    def passes_threshold(self) -> bool:
        """Check if correction rate meets < 20% target."""
        return self.correction_rate < 20.0

    @property
    def rating(self) -> str:
        """Rate the plan based on correction rate."""
        rate = self.correction_rate
        if rate < 10:
            return "Excellent - Minimal corrections needed"
        elif rate < 20:
            return "Good - Meets target"
        elif rate < 30:
            return "Acceptable - Slightly above target"
        elif rate < 50:
            return "Poor - Significant corrections needed"
        else:
            return "Failing - Major rework required"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_items': self.total_items,
            'items_added': self.items_added,
            'items_removed': self.items_removed,
            'items_modified': self.items_modified,
            'items_unchanged': self.items_unchanged,
            'correction_rate': self.correction_rate,
            'passes_threshold': self.passes_threshold,
            'rating': self.rating
        }


class CorrectionTracker:
    """
    Tracks manual corrections to plans.

    Two modes:
    1. Diff-based: Compare generated plan to manually corrected version
    2. Annotation-based: Use JSON annotations of corrections made
    """

    def __init__(self):
        pass

    def track_from_diff(self, generated_plan_path: Path, corrected_plan_path: Path) -> CorrectionMetrics:
        """
        Track corrections by diffing generated vs corrected plan.

        Uses structured sections to identify plan items (e.g., bullet points, numbered steps).
        """
        with open(generated_plan_path) as f:
            generated = f.read()

        with open(corrected_plan_path) as f:
            corrected = f.read()

        # Extract plan items from both
        generated_items = self._extract_plan_items(generated)
        corrected_items = self._extract_plan_items(corrected)

        return self._calculate_corrections(generated_items, corrected_items)

    def track_from_annotations(self, annotations_path: Path) -> CorrectionMetrics:
        """
        Track corrections from a JSON annotation file.

        Expected format:
        {
          "corrections": [
            {"type": "add", "item": "Added task description"},
            {"type": "remove", "item": "Removed task description"},
            {"type": "modify", "before": "Original", "after": "Modified"}
          ]
        }
        """
        with open(annotations_path) as f:
            data = json.load(f)

        corrections = data.get('corrections', [])

        metrics = CorrectionMetrics()
        metrics.total_items = data.get('total_items', len(corrections))

        for correction in corrections:
            cor_type = correction.get('type', 'modify')
            if cor_type == 'add':
                metrics.items_added += 1
            elif cor_type == 'remove':
                metrics.items_removed += 1
            elif cor_type == 'modify':
                metrics.items_modified += 1

        metrics.items_unchanged = metrics.total_items - (
            metrics.items_added + metrics.items_removed + metrics.items_modified
        )

        return metrics

    def _extract_plan_items(self, plan: str) -> List[str]:
        """
        Extract structured plan items from markdown.

        Looks for:
        - Bullet points (-, *, +)
        - Numbered lists (1., 2.)
        - Task items under specific headings
        """
        import re

        items = []

        # Split into lines and process
        lines = plan.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()

            # Track sections (to ignore non-plan content)
            if line.startswith('#'):
                current_section = line.lower()
                continue

            # Skip non-plan sections (like summaries, notes)
            if current_section and any(skip in current_section for skip in ['summary', 'background', 'note']):
                continue

            # Match plan items
            patterns = [
                r'^[\-\*\+]\s+(.+)$',  # Bullet points
                r'^\d+\.\s+(.+)$',  # Numbered lists
            ]

            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    item = match.group(1).strip()
                    # Filter out very short items (likely headers)
                    if len(item) > 10:
                        items.append(item)
                    break

        return items

    def _calculate_corrections(self, generated: List[str], corrected: List[str]) -> CorrectionMetrics:
        """
        Calculate correction metrics by comparing item lists.

        Uses sequence matching to identify adds, removes, and modifications.
        """
        metrics = CorrectionMetrics()

        # Use difflib to compare sequences
        matcher = difflib.SequenceMatcher(None, generated, corrected)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Items unchanged
                metrics.items_unchanged += (i2 - i1)
            elif tag == 'replace':
                # Items modified
                metrics.items_modified += max(i2 - i1, j2 - j1)
            elif tag == 'delete':
                # Items removed
                metrics.items_removed += (i2 - i1)
            elif tag == 'insert':
                # Items added
                metrics.items_added += (j2 - j1)

        # Total items is from the generated plan (baseline)
        metrics.total_items = len(generated)

        return metrics

    def create_annotation_template(self, plan_path: Path, output_path: Path):
        """
        Create a template annotation file for manual correction tracking.

        Users fill this out as they correct the plan.
        """
        with open(plan_path) as f:
            plan = f.read()

        items = self._extract_plan_items(plan)

        template = {
            "total_items": len(items),
            "corrections": [
                # Examples for user to follow
                {"type": "modify", "item_index": 0, "before": "Original text", "after": "Corrected text", "reason": "Why changed"},
                {"type": "remove", "item_index": 1, "reason": "Why removed"},
                {"type": "add", "item": "New item added", "reason": "Why added"}
            ],
            "plan_items": [
                {"index": i, "text": item}
                for i, item in enumerate(items)
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(template, f, indent=2)

        print(f"Template created with {len(items)} plan items")
        print(f"Edit {output_path} to record your corrections")

    def generate_report(self, metrics: CorrectionMetrics, title: str = "Correction Analysis") -> str:
        """Generate human-readable correction report."""
        report = []
        report.append(f"# {title}\n")
        report.append(f"**Correction Rate**: {metrics.correction_rate:.1f}% {'✓ PASS' if metrics.passes_threshold else '✗ FAIL'}")
        report.append(f"**Rating**: {metrics.rating}\n")

        report.append("## Correction Breakdown\n")
        report.append(f"- **Total Plan Items**: {metrics.total_items}")
        report.append(f"- **Unchanged**: {metrics.items_unchanged} ({metrics.items_unchanged/metrics.total_items*100 if metrics.total_items > 0 else 0:.1f}%)")
        report.append(f"- **Modified**: {metrics.items_modified} ({metrics.items_modified/metrics.total_items*100 if metrics.total_items > 0 else 0:.1f}%)")
        report.append(f"- **Added**: {metrics.items_added}")
        report.append(f"- **Removed**: {metrics.items_removed}\n")

        report.append("## Interpretation\n")
        if metrics.passes_threshold:
            report.append("✓ This plan meets the < 20% correction threshold.")
            report.append("  The generated plan requires minimal human intervention.")
        else:
            report.append("✗ This plan exceeds the 20% correction threshold.")
            report.append("  Consider improving plan generation quality.")
            report.append(f"  Need to reduce corrections by {metrics.correction_rate - 20:.1f}% to meet target.")

        return "\n".join(report)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Create template: python correction_tracker.py template <plan_file> <output_annotations.json>")
        print("  Track from diff: python correction_tracker.py diff <generated_plan> <corrected_plan>")
        print("  Track from annotations: python correction_tracker.py annotations <annotations.json>")
        sys.exit(1)

    tracker = CorrectionTracker()
    mode = sys.argv[1]

    if mode == "template":
        if len(sys.argv) < 4:
            print("Error: Need plan file and output path")
            sys.exit(1)

        plan_path = Path(sys.argv[2])
        output_path = Path(sys.argv[3])
        tracker.create_annotation_template(plan_path, output_path)

    elif mode == "diff":
        if len(sys.argv) < 4:
            print("Error: Need generated and corrected plan files")
            sys.exit(1)

        generated = Path(sys.argv[2])
        corrected = Path(sys.argv[3])
        metrics = tracker.track_from_diff(generated, corrected)

        print(tracker.generate_report(metrics))

        # Save JSON
        output_path = generated.parent / "correction_metrics.json"
        with open(output_path, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)

        print(f"\nMetrics saved to: {output_path}")

    elif mode == "annotations":
        if len(sys.argv) < 3:
            print("Error: Need annotations file")
            sys.exit(1)

        annotations = Path(sys.argv[2])
        metrics = tracker.track_from_annotations(annotations)

        print(tracker.generate_report(metrics))

        # Save JSON
        output_path = annotations.parent / "correction_metrics.json"
        with open(output_path, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)

        print(f"\nMetrics saved to: {output_path}")

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
