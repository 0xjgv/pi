#!/usr/bin/env python3
"""
Main evaluation runner for π CLI.

Executes test scenarios, analyzes results, and generates comprehensive reports.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from plan_analyzer import PlanAnalyzer, PlanQualityScore
from review_analyzer import ReviewAnalyzer, ReviewFeedback
from correction_tracker import CorrectionTracker, CorrectionMetrics


class EvaluationRunner:
    """Orchestrates evaluation of π CLI across test scenarios."""

    def __init__(self, scenarios_dir: Path, results_dir: Path):
        self.scenarios_dir = scenarios_dir
        self.results_dir = results_dir
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = results_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def run_all_scenarios(self) -> Dict[str, Any]:
        """Run evaluation on all scenarios."""
        scenarios = sorted(self.scenarios_dir.glob("*/scenario.json"))

        print(f"Found {len(scenarios)} scenarios")
        print(f"Results will be saved to: {self.run_dir}\n")

        results = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'scenarios': {},
            'summary': {}
        }

        for scenario_file in scenarios:
            scenario_dir = scenario_file.parent
            scenario_id = scenario_dir.name

            print(f"{'='*60}")
            print(f"Running scenario: {scenario_id}")
            print(f"{'='*60}")

            result = self.run_scenario(scenario_dir)
            results['scenarios'][scenario_id] = result

            print(f"\n✓ Scenario complete: {scenario_id}")
            print(f"  Quality Score: {result['quality_score']['total_score']}/100 ({result['quality_score']['rating']})")
            print(f"  Review Points: {result['review_feedback']['total_points']}")
            print()

        # Calculate summary metrics
        results['summary'] = self._calculate_summary(results['scenarios'])

        # Save results
        with open(self.run_dir / "results.json", 'w') as f:
            json.dump(results, f, indent=2)

        # Generate report
        report = self._generate_summary_report(results)
        with open(self.run_dir / "REPORT.md", 'w') as f:
            f.write(report)

        print(f"\n{'='*60}")
        print("EVALUATION COMPLETE")
        print(f"{'='*60}")
        print(f"Results saved to: {self.run_dir}")
        print(f"\nSummary:")
        print(f"  Average Quality Score: {results['summary']['avg_quality_score']:.1f}/100")
        print(f"  Scenarios Passing (≥80): {results['summary']['scenarios_passing']}/{results['summary']['total_scenarios']}")
        print(f"  Average Review Points: {results['summary']['avg_review_points']:.1f}")

        return results

    def run_scenario(self, scenario_dir: Path) -> Dict[str, Any]:
        """Run evaluation for a single scenario."""
        with open(scenario_dir / "scenario.json") as f:
            scenario = json.load(f)

        scenario_id = scenario['id']
        prompt = scenario['prompt']

        # Create output directory for this scenario
        output_dir = self.run_dir / scenario_id
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {
            'scenario_id': scenario_id,
            'category': scenario['category'],
            'difficulty': scenario['difficulty'],
            'description': scenario['description']
        }

        # Step 1: Run π CLI with the prompt
        print(f"\n[1/5] Executing π CLI...")
        workflow_result = self._run_cli(prompt, output_dir)
        result['workflow'] = workflow_result

        if not workflow_result['success']:
            print(f"  ✗ CLI execution failed: {workflow_result['error']}")
            result['error'] = workflow_result['error']
            return result

        print(f"  ✓ Workflow completed (ID: {workflow_result['workflow_id']})")

        # Step 2: Analyze plan quality
        print(f"\n[2/5] Analyzing plan quality...")
        plan_analyzer = PlanAnalyzer(scenario_dir)

        # Find the generated plan
        plan_path = self._find_plan_file(workflow_result['workflow_id'])
        if plan_path:
            quality_score = plan_analyzer.analyze_plan(plan_path)
            result['quality_score'] = quality_score.to_dict()

            # Save quality report
            quality_report = plan_analyzer.generate_report(quality_score)
            with open(output_dir / "quality_report.md", 'w') as f:
                f.write(quality_report)

            print(f"  ✓ Quality Score: {quality_score.total_score}/100 ({quality_score.rating})")
        else:
            print(f"  ✗ Could not find generated plan")
            result['quality_score'] = None

        # Step 3: Analyze review feedback
        print(f"\n[3/5] Analyzing review feedback...")
        review_analyzer = ReviewAnalyzer()

        review_path = self._find_review_file(workflow_result['workflow_id'])
        if review_path:
            review_feedback = review_analyzer.analyze_review(review_path)
            result['review_feedback'] = review_feedback.to_dict()

            # Save review analysis
            review_report = review_analyzer.generate_report(review_feedback, "Review Feedback Analysis")
            with open(output_dir / "review_analysis.md", 'w') as f:
                f.write(review_report)

            print(f"  ✓ Found {review_feedback.total_points} feedback points (avg severity: {review_feedback.avg_severity})")
        else:
            print(f"  ✗ Could not find review document")
            result['review_feedback'] = None

        # Step 4: Analyze iteration effectiveness
        print(f"\n[4/5] Analyzing iteration effectiveness...")
        iterated_plan_path = self._find_iterated_plan_file(workflow_result['workflow_id'])

        if iterated_plan_path and plan_path:
            iterated_quality = plan_analyzer.analyze_plan(iterated_plan_path)
            result['iterated_quality_score'] = iterated_quality.to_dict()

            # Calculate improvement
            improvement = {
                'quality_improvement': iterated_quality.total_score - quality_score.total_score,
                'before': quality_score.total_score,
                'after': iterated_quality.total_score
            }
            result['quality_improvement'] = improvement

            print(f"  ✓ Quality improved by {improvement['quality_improvement']} points ({quality_score.total_score} → {iterated_quality.total_score})")
        else:
            print(f"  ⚠ Iteration analysis skipped (missing files)")
            result['iterated_quality_score'] = None
            result['quality_improvement'] = None

        # Step 5: Manual correction tracking (requires human input)
        print(f"\n[5/5] Preparing correction tracking...")
        if iterated_plan_path:
            tracker = CorrectionTracker()
            template_path = output_dir / "correction_template.json"
            tracker.create_annotation_template(iterated_plan_path, template_path)
            print(f"  ✓ Correction template created: {template_path}")
            print(f"     Fill this out after manually reviewing the plan to track corrections")
            result['correction_template'] = str(template_path)
        else:
            print(f"  ⚠ Correction tracking skipped")

        return result

    def _run_cli(self, prompt: str, output_dir: Path) -> Dict[str, Any]:
        """
        Execute π CLI with the given prompt.

        Returns workflow metadata and status.
        """
        try:
            # Construct CLI command
            cli_path = Path(__file__).parent.parent.parent / "π" / "cli.py"

            cmd = [sys.executable, str(cli_path), prompt]

            # Run CLI and capture output
            start_time = time.time()
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            duration = time.time() - start_time

            # Save CLI output
            with open(output_dir / "cli_output.txt", 'w') as f:
                f.write(f"STDOUT:\n{process.stdout}\n\n")
                f.write(f"STDERR:\n{process.stderr}\n")

            # Extract workflow ID from output (assuming it's logged)
            workflow_id = self._extract_workflow_id(process.stdout)

            return {
                'success': process.returncode == 0,
                'workflow_id': workflow_id,
                'duration_seconds': duration,
                'return_code': process.returncode,
                'stdout': process.stdout[:1000],  # Truncate for JSON
                'stderr': process.stderr[:1000]
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'CLI execution timed out after 10 minutes'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _extract_workflow_id(self, output: str) -> Optional[str]:
        """Extract workflow ID from CLI output."""
        import re
        # Look for UUID pattern
        match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', output, re.IGNORECASE)
        if match:
            return match.group(0)
        return None

    def _find_plan_file(self, workflow_id: Optional[str]) -> Optional[Path]:
        """Find the generated plan file for a workflow."""
        if not workflow_id:
            return None

        thoughts_dir = Path.cwd() / "thoughts" / workflow_id
        if not thoughts_dir.exists():
            return None

        # Look for plan-*.md
        plans = list(thoughts_dir.glob("plan-*.md"))
        return plans[0] if plans else None

    def _find_review_file(self, workflow_id: Optional[str]) -> Optional[Path]:
        """Find the review file for a workflow."""
        if not workflow_id:
            return None

        thoughts_dir = Path.cwd() / "thoughts" / workflow_id
        if not thoughts_dir.exists():
            return None

        # Look for review-*.md
        reviews = list(thoughts_dir.glob("review-*.md"))
        return reviews[0] if reviews else None

    def _find_iterated_plan_file(self, workflow_id: Optional[str]) -> Optional[Path]:
        """Find the iterated plan file for a workflow."""
        if not workflow_id:
            return None

        thoughts_dir = Path.cwd() / "thoughts" / workflow_id
        if not thoughts_dir.exists():
            return None

        # Look for iterate-*.md or final-plan-*.md
        iterated = list(thoughts_dir.glob("iterate-*.md")) + list(thoughts_dir.glob("final-plan-*.md"))
        return iterated[0] if iterated else None

    def _calculate_summary(self, scenarios: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics across all scenarios."""
        quality_scores = [
            s['quality_score']['total_score']
            for s in scenarios.values()
            if s.get('quality_score')
        ]

        review_points = [
            s['review_feedback']['total_points']
            for s in scenarios.values()
            if s.get('review_feedback')
        ]

        quality_improvements = [
            s['quality_improvement']['quality_improvement']
            for s in scenarios.values()
            if s.get('quality_improvement')
        ]

        return {
            'total_scenarios': len(scenarios),
            'successful_runs': sum(1 for s in scenarios.values() if s.get('workflow', {}).get('success')),
            'avg_quality_score': sum(quality_scores) / len(quality_scores) if quality_scores else 0,
            'min_quality_score': min(quality_scores) if quality_scores else 0,
            'max_quality_score': max(quality_scores) if quality_scores else 0,
            'scenarios_passing': sum(1 for score in quality_scores if score >= 80),
            'avg_review_points': sum(review_points) / len(review_points) if review_points else 0,
            'avg_quality_improvement': sum(quality_improvements) / len(quality_improvements) if quality_improvements else 0
        }

    def _generate_summary_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive summary report in markdown."""
        summary = results['summary']

        report = []
        report.append("# π CLI Evaluation Report\n")
        report.append(f"**Run ID**: {results['run_id']}")
        report.append(f"**Timestamp**: {results['timestamp']}\n")

        report.append("## Executive Summary\n")
        report.append(f"- **Total Scenarios**: {summary['total_scenarios']}")
        report.append(f"- **Successful Runs**: {summary['successful_runs']}/{summary['total_scenarios']}")
        report.append(f"- **Average Quality Score**: {summary['avg_quality_score']:.1f}/100")
        report.append(f"- **Scenarios Meeting Threshold (≥80)**: {summary['scenarios_passing']}/{summary['total_scenarios']} ({summary['scenarios_passing']/summary['total_scenarios']*100 if summary['total_scenarios'] > 0 else 0:.1f}%)")
        report.append(f"- **Average Review Feedback Points**: {summary['avg_review_points']:.1f}")
        report.append(f"- **Average Quality Improvement (iteration)**: {summary['avg_quality_improvement']:.1f} points\n")

        # Overall assessment
        report.append("## Overall Assessment\n")
        if summary['avg_quality_score'] >= 80 and summary['scenarios_passing'] / summary['total_scenarios'] >= 0.8:
            report.append("✓ **PASS** - π CLI generates high-quality plans consistently\n")
        elif summary['avg_quality_score'] >= 70:
            report.append("⚠ **MARGINAL** - π CLI generates acceptable plans but needs improvement\n")
        else:
            report.append("✗ **FAIL** - π CLI plan quality below acceptable threshold\n")

        # Per-scenario details
        report.append("## Scenario Results\n")
        for scenario_id, result in results['scenarios'].items():
            report.append(f"### {scenario_id}")
            report.append(f"- **Category**: {result['category']}")
            report.append(f"- **Difficulty**: {result['difficulty']}")
            report.append(f"- **Description**: {result['description']}")

            if result.get('workflow', {}).get('success'):
                qs = result.get('quality_score', {})
                report.append(f"- **Quality Score**: {qs.get('total_score', 'N/A')}/100 ({qs.get('rating', 'N/A')})")

                rf = result.get('review_feedback', {})
                report.append(f"- **Review Points**: {rf.get('total_points', 'N/A')} ({rf.get('avg_severity', 'N/A')} avg severity)")

                if result.get('quality_improvement'):
                    qi = result['quality_improvement']
                    report.append(f"- **Iteration Improvement**: +{qi['quality_improvement']} points ({qi['before']} → {qi['after']})")
            else:
                report.append(f"- **Status**: ✗ Failed - {result.get('error', 'Unknown error')}")

            report.append("")

        # Recommendations
        report.append("## Recommendations\n")
        if summary['avg_quality_score'] < 80:
            report.append("1. **Improve Plan Completeness**: Focus on identifying all affected files and dependencies")
        if summary['avg_review_points'] > 5:
            report.append("2. **Reduce Review Feedback**: Plans are generating significant review feedback - improve initial quality")
        if summary['avg_quality_improvement'] < 5:
            report.append("3. **Strengthen Iteration**: Iteration stage not significantly improving plans")

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Run π CLI evaluation")
    parser.add_argument(
        "--scenario",
        help="Run specific scenario (e.g., 01_bug_fix)",
        default=None
    )
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=Path(__file__).parent / "scenarios",
        help="Directory containing test scenarios"
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).parent / "results",
        help="Directory to save results"
    )

    args = parser.parse_args()

    runner = EvaluationRunner(args.scenarios_dir, args.results_dir)

    if args.scenario:
        # Run single scenario
        scenario_dir = args.scenarios_dir / args.scenario
        if not scenario_dir.exists():
            print(f"Error: Scenario not found: {args.scenario}")
            sys.exit(1)

        result = runner.run_scenario(scenario_dir)
        print("\nResult:", json.dumps(result, indent=2))
    else:
        # Run all scenarios
        results = runner.run_all_scenarios()

        # Print report
        with open(runner.run_dir / "REPORT.md") as f:
            print(f"\n{f.read()}")


if __name__ == "__main__":
    main()
