"""Gate an evaluation report against a stored baseline report.

Fails (exit 1) when:
  * any evaluator's mean score drops more than --tolerance below the baseline, or
  * any --must-pass evaluator has a failed row.

Both files use the JSON written by `evaluation/evaluate.py --wait --report`.

Usage (from sample/):
    # Once, from a known-good run on main:
    python evaluation/compare_to_baseline.py --report drift-summary.json \
        --baseline evaluation/baselines/drift-lockbox.json --write-baseline

    # In CI, on every pull request:
    python evaluation/compare_to_baseline.py --report drift-summary.json \
        --baseline evaluation/baselines/drift-lockbox.json \
        --tolerance 0.03 --must-pass next_action_success
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def by_name(report: dict) -> dict[str, dict]:
    if not report.get("results_complete"):
        raise SystemExit("Report is incomplete; the evaluation did not finish cleanly.")
    return {criterion["name"]: criterion for criterion in report["criteria"]}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.03,
        help="Allowed drop in mean score. Foundry treats changes under 0.03 as noise.",
    )
    parser.add_argument(
        "--must-pass",
        nargs="*",
        default=[],
        help="Evaluators where any failed row blocks the change.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Save this report as the new baseline instead of comparing.",
    )
    args = parser.parse_args()

    report = json.loads(args.report.read_text())
    current = by_name(report)

    if args.write_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.report, args.baseline)
        print(f"Baseline written to {args.baseline}")
        return 0

    if not args.baseline.is_file():
        print(
            f"FAIL: no baseline at {args.baseline}. "
            "Run a known-good version once with --write-baseline."
        )
        return 1
    baseline = by_name(json.loads(args.baseline.read_text()))

    failures = []
    print(f"{'Evaluator':<28}{'Baseline':>10}{'This run':>10}{'Change':>10}  Failed rows")
    for name, base in sorted(baseline.items()):
        if name not in current:
            failures.append(f"{name}: missing from this run")
            continue
        now = current[name]
        change = now["mean_score"] - base["mean_score"]
        print(
            f"{name:<28}{base['mean_score']:>10.3f}{now['mean_score']:>10.3f}{change:>+10.3f}  "
            f"{now['failed']}/{now['total']}"
        )
        if change < -args.tolerance:
            failures.append(
                f"{name}: mean dropped {-change:.3f}, more than the {args.tolerance} noise band"
            )
        if name in args.must_pass and now["failed"] > 0:
            failures.append(f"{name}: {now['failed']} must-pass row(s) failed")

    if failures:
        print("\nFAIL:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nOK: no drop beyond the noise band and no must-pass failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
