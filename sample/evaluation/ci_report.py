"""CI support for evaluate.py: baseline compatibility, waiting for results and the score report.

Not needed to follow the demo. The report JSON is what compare_to_baseline.py gates on.
"""

import hashlib
import json
import time
from math import isfinite
from pathlib import Path
from statistics import fmean

from compare_to_baseline import provenance_errors
from openai import OpenAI


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def provenance(rows: list[dict], evaluation: dict) -> dict:
    """What a score depends on: the exact questions and each judge's definition and inputs."""
    return {
        "dataset_sha256": fingerprint(rows),
        "judges": {
            criterion["name"]: {
                "evaluator_name": criterion["evaluator_name"],
                "definition_sha256": fingerprint(
                    json.loads(
                        (Path(__file__).parent / f"{criterion['evaluator_name']}.json").read_text()
                    )["definition"]
                ),
                "initialization_parameters": criterion["initialization_parameters"],
                "data_mapping": criterion["data_mapping"],
            }
            for criterion in evaluation["testing_criteria"]
        },
    }


def check_baseline(baseline: Path, rows: list[dict], evaluation: dict) -> None:
    errors = provenance_errors(
        {"provenance": provenance(rows, evaluation)}, json.loads(baseline.read_text())
    )
    if errors:
        raise SystemExit("FAIL: " + "\n".join(errors))


def judge_problems(client: OpenAI, run_id: str, eval_id: str, name: str) -> list[str]:
    """Which questions an evaluator errored on or skipped, and what it said."""
    lines = [f"Questions where {name} did not score:"]
    for item in client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=100):
        data = item.model_dump(warnings=False)
        question = (data.get("datasource_item") or {}).get("name", item.id)
        for result in data.get("results") or []:
            if result.get("name") != name:
                continue
            if result.get("status") not in (None, "completed") or result.get("error"):
                error = result.get("error") or (result.get("sample") or {}).get("error")
                if isinstance(error, dict):
                    error = error.get("message", error)
                detail = error or result.get("reason") or result.get("status")
                lines.append(f"  {question}: {str(detail)[:300]}")
    return lines


def wait_for_evaluation(
    client: OpenAI,
    run_id: str,
    *,
    agent_name: str,
    evaluation: dict,
    rows: list[dict],
    report_path: Path | None,
    max_unscored: int = 0,
) -> None:
    eval_id = evaluation["id"]
    expected_rows = len(rows)
    expected_criteria = {criterion["name"] for criterion in evaluation["testing_criteria"]}
    report = {
        "agent_name": agent_name,
        "eval_id": eval_id,
        "run_id": run_id,
        "status": None,
        "results_complete": False,
        "provenance": provenance(rows, evaluation),
        "evaluator_versions": {
            criterion["name"]: criterion["evaluator_version"]
            for criterion in evaluation["testing_criteria"]
        },
    }

    deadline = time.monotonic() + 3600
    run = client.evals.runs.retrieve(run_id, eval_id=eval_id)
    while run.status in ("queued", "in_progress"):
        report["status"] = run.status
        if report_path:
            report_path.write_text(json.dumps(report, indent=2) + "\n")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Evaluation {run_id} did not finish within 60 minutes; it may still be running."
            )
        print(f"Waiting for evaluation: {run.status}", flush=True)
        time.sleep(30)
        run = client.evals.runs.retrieve(run_id, eval_id=eval_id)

    report["status"] = run.status
    report["report_url"] = run.report_url
    report["result_counts"] = run.result_counts.model_dump()
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    if run.status != "completed":
        raise RuntimeError(f"Evaluation {run_id} ended with status {run.status}: {run.error}")
    # The agent must have answered every question; a judge may miss a few (see --max-unscored).
    if run.error is not None or run.result_counts.total != expected_rows:
        raise RuntimeError(f"Evaluation {run_id} is incomplete: {run.result_counts}")

    scores: dict[str, list[float]] = {name: [] for name in expected_criteria}
    passes = dict.fromkeys(expected_criteria, 0)
    unscored = dict.fromkeys(expected_criteria, 0)
    items = list(client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=100))
    if len(items) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} evaluation rows, received {len(items)}")
    for item in items:
        if item.sample.error is not None:
            raise RuntimeError(f"The agent failed on evaluation row {item.id}: {item.sample.error}")
        results = {r.get("name"): r for r in item.model_dump(warnings=False)["results"] or []}
        for name in expected_criteria:
            result = results.get(name, {})
            score, passed = result.get("score"), result.get("passed")
            if (
                result.get("status") not in (None, "completed")
                or result.get("error") is not None
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not isfinite(score)
                or not isinstance(passed, bool)
            ):
                unscored[name] += 1
                continue
            scores[name].append(score)
            passes[name] += int(passed)

    for name, missed in unscored.items():
        if missed == 0:
            continue
        for line in judge_problems(client, run_id, eval_id, name):
            print(line, flush=True)
        if missed > max_unscored:
            raise RuntimeError(
                f"{name} did not score {missed} question(s), more than --max-unscored "
                f"{max_unscored}; see above. A 429 is the judge model's rate limit: re-run. "
                "A 401 means you lack account-level Foundry User (new roles take ~10 minutes)."
            )
        print(
            f"WARNING: {name} did not score {missed} question(s); its averages use the other "
            f"{expected_rows - missed}.",
            flush=True,
        )

    report["criteria"] = [
        {
            "name": name,
            "mean_score": fmean(scores[name]),
            "passed": passes[name],
            "failed": len(scores[name]) - passes[name],
            "total": len(scores[name]),
            "unscored": unscored[name],
        }
        for name in sorted(expected_criteria)
    ]
    report["results_complete"] = True
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
