"""Compare evaluation runs question by question: what did a change actually fix or break?

Give one or more runs of the old version (A) and of the new version (B). Several runs per side
is better: answers vary, so a question only counts as fixed if it failed in every A run and
passed in every B run. Each run is either an exported results file (.jsonl, downloaded from
the run in Foundry) or a run in your project, written as EVAL_ID:RUN_ID.

Run from sample/:

    # 1. Find the runs (needs FOUNDRY_PROJECT_ENDPOINT, as for evaluate.py):
    python evaluation/compare_runs.py --list

    # 2. Compare: two baseline runs against two runs of the new prompt:
    python evaluation/compare_runs.py \\
        --a EVAL_ID:RUN_ID_1 EVAL_ID:RUN_ID_2 \\
        --b EVAL_ID:RUN_ID_3 EVAL_ID:RUN_ID_4

    # Exported files work the same way, with no Azure access needed:
    python evaluation/compare_runs.py --a old-1.jsonl old-2.jsonl --b new-1.jsonl new-2.jsonl

It prints the questions B fixed, the ones it broke, the flaky ones (different results within
a side), and the question text of the fixed ones: good candidates to ask live in a demo.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

JUDGE = "next_action_success"


def rows_from_file(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def openai_client():
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint.startswith("https://"):
        sys.exit(
            "FOUNDRY_PROJECT_ENDPOINT is not set. From sample/, run:\n"
            '  export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)"'
        )
    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    return project.get_openai_client()


def rows_from_run(client, ref: str) -> list[dict]:
    eval_id, _, run_id = ref.partition(":")
    if not run_id:
        sys.exit(f"{ref!r}: write a run as EVAL_ID:RUN_ID (see --list), or give a .jsonl file.")
    items = client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=100)
    return [item.model_dump(warnings=False) for item in items]


def load(refs: list[str], client_box: list) -> list[dict[str, tuple[bool | None, str]]]:
    """One {question name: (passed, question text)} per run; None when the judge didn't score."""
    runs = []
    for ref in refs:
        if ref.endswith(".jsonl"):
            rows = rows_from_file(Path(ref))
        else:
            if not client_box:
                client_box.append(openai_client())
            rows = rows_from_run(client_box[0], ref)
        run = {}
        for row in rows:
            item = row.get("datasource_item") or {}
            judged = [r for r in row.get("results") or [] if r.get("name") == JUDGE]
            passed = judged[0].get("passed") if judged else None
            run[item.get("name", row.get("id"))] = (passed, item.get("query", ""))
        runs.append(run)
    return runs


def list_runs() -> None:
    client = openai_client()
    print(f"{'Run (pass to --a / --b)':<75} {'Created':<17} Passed")
    for evaluation in client.evals.list(limit=20, order="desc"):
        for run in client.evals.runs.list(evaluation.id, limit=10, order="desc"):
            counts = run.result_counts
            created = datetime.fromtimestamp(run.created_at)
            passed = f"{counts.passed}/{counts.total}" if counts else "-"
            print(f"{evaluation.id}:{run.id:<40} {created:%d %b %H:%M}  {passed}  {run.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", action="store_true", help="List recent runs and exit.")
    parser.add_argument("--a", nargs="+", default=[], help="Runs of the old version.")
    parser.add_argument("--b", nargs="+", default=[], help="Runs of the new version.")
    args = parser.parse_args()
    if args.list:
        list_runs()
        return
    if not args.a or not args.b:
        parser.error("give at least one run for --a and one for --b (or use --list)")

    box: list = []
    a_runs, b_runs = load(args.a, box), load(args.b, box)
    names = sorted(set().union(*a_runs, *b_runs))
    text = {n: q for run in a_runs + b_runs for n, (_, q) in run.items() if q}

    def marks(runs, name):
        return [run.get(name, (None, ""))[0] for run in runs]

    fixed, broken, flaky = [], [], []
    for name in names:
        a, b = marks(a_runs, name), marks(b_runs, name)
        if None in a or None in b:
            continue
        if len(set(a)) > 1 or len(set(b)) > 1:
            flaky.append(name)
        elif a[0] is False and b[0] is True:
            fixed.append(name)
        elif a[0] is True and b[0] is False:
            broken.append(name)

    def score(runs):
        results = [p for run in runs for p, _ in run.values() if p is not None]
        return f"{sum(results)}/{len(results)} passed"

    print(f"A ({len(a_runs)} run(s)): {score(a_runs)}    B ({len(b_runs)} run(s)): {score(b_runs)}")
    print(f"Judge: {JUDGE}. A question counts only if it gave the same result in every run.")
    if len(a_runs) == 1 or len(b_runs) == 1:
        print(
            "Note: with only one run on a side, 'fixed' and 'broken' can't be told apart from "
            "run-to-run noise.\nGive each side two or more runs; noisy questions then show as "
            "flaky."
        )
    print()
    for title, group in (("Fixed by B", fixed), ("Broken by B", broken), ("Flaky", flaky)):
        print(f"{title} ({len(group)}):")
        for name in group:
            print(f"  {name}   A {marks(a_runs, name)}  B {marks(b_runs, name)}")
        print()
    if fixed:
        print("Demo candidates (failed in every A run, passed in every B run):")
        for name in fixed:
            print(f"  {name}\n    {text.get(name, '')}")


if __name__ == "__main__":
    main()
