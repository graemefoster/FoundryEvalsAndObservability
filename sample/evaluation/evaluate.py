# Evaluate the agent's next action, not just whether it can quote a policy.
# This script submits the experiment. Foundry calls the agent and judges its answers.

import argparse
import json
import os
import time
from contextlib import ExitStack
from math import isfinite
from pathlib import Path
from statistics import fmean

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai import OpenAI

# The agent answers the questions; a separate model acts as the judge.
# Agent and evaluator versions default to latest.
AGENT_NAME = "purchasing-advice-demo"
EVALUATOR_NAME = "purchasing-next-action"
RUBRIC_NAME = "purchasing-demo-rubric"
JUDGE_MODEL = "gpt-5.5"
DATASET = Path(__file__).resolve().parent / "datasets/golden-development.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the hosted demo agent (billable).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print requests; no cloud calls.")
    mode.add_argument(
        "--register-only", action="store_true", help="Ensure evaluators exist; no scoring run."
    )
    parser.add_argument(
        "--wait", action="store_true", help="Wait for results; fail on execution errors."
    )
    parser.add_argument(
        "--report", type=Path, help="Write a score summary JSON file; requires --wait."
    )
    args = parser.parse_args()
    if args.wait and (args.dry_run or args.register_only):
        parser.error("--wait requires an evaluation run")
    if args.report and not args.wait:
        parser.error("--report requires --wait")

    with ExitStack() as stack:
        # 1. Ensure both evaluators exist, except during the offline dry run.
        if not args.dry_run:
            credential = stack.enter_context(DefaultAzureCredential())
            project = stack.enter_context(
                AIProjectClient(
                    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
                )
            )
            ensure_evaluator(project, "purchasing-next-action.json", EVALUATOR_NAME)
            ensure_evaluator(project, "purchasing-demo-rubric.json", RUBRIC_NAME)
            if args.register_only:
                return

        # 2. Load the questions and references; the agent answers are generated during the run.
        rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]

        # 3. Define the evaluation and map its inputs.
        evaluation = {
            "name": "purchasing-next-action-evaluation-development",
            "data_source_config": {
                "type": "custom",
                "item_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "query": {"type": "string"},
                        "ground_truth": {"type": "string"},
                    },
                    "required": ["name", "query", "ground_truth"],
                    "additionalProperties": False,
                },
                # Also make the agent's generated output available to the judge.
                "include_sample_schema": True,
            },
            "testing_criteria": [
                {
                    "type": "azure_ai_evaluator",
                    "name": "next_action_success",
                    "evaluator_name": EVALUATOR_NAME,
                    # The prompt judge returns 1 for the correct next action, otherwise 0.
                    "initialization_parameters": {
                        "deployment_name": JUDGE_MODEL,
                        "threshold": 1,
                    },
                    # The prompt judge sees the question, reference and actual answer.
                    "data_mapping": {
                        "query": "{{item.query}}",
                        "ground_truth": "{{item.ground_truth}}",
                        "response": "{{sample.output_text}}",
                    },
                },
                {
                    "type": "azure_ai_evaluator",
                    "name": "purchasing_behaviour",
                    "evaluator_name": RUBRIC_NAME,
                    "initialization_parameters": {"model": JUDGE_MODEL},
                    # Native rubric scores behaviour without the reference answer.
                    "data_mapping": {
                        "query": "{{item.query}}",
                        "response": "{{sample.output_text}}",
                    },
                },
            ],
        }
        # 4. Target the deployed agent, including its tools, with only the question.
        data_source = {
            "type": "azure_ai_target_completions",
            "source": {
                "type": "file_content",
                "content": [{"item": row} for row in rows],
            },
            "input_messages": {
                "type": "template",
                "template": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": {"type": "input_text", "text": "{{item.query}}"},
                    }
                ],
            },
            "target": {
                "type": "azure_ai_agent",
                "name": AGENT_NAME,
            },
        }
        if args.dry_run:
            print(json.dumps({"evaluation": evaluation, "data_source": data_source}, indent=2))
            return

        with project.get_openai_client() as client:
            # Save the evaluation definition without generating agent answers.
            result = client.evals.create(**evaluation)
            print(f"Eval ID: {result.id}", flush=True)

            # 5. Start the billable run: Foundry generates answers and applies the judges.
            run = client.evals.runs.create(
                eval_id=result.id,
                name=evaluation["name"],
                data_source=data_source,
            )
            # Submission is not completion. Follow the report in Foundry.
            print(f"Run ID: {run.id}", flush=True)
            print(f"Status: {run.status}")
            if run.report_url:
                print(f"Report: {run.report_url}")
            print("View progress, answers and scores in Foundry Evaluations.")
            if args.wait:
                wait_for_evaluation(
                    client,
                    result.id,
                    run.id,
                    expected_rows=len(rows),
                    expected_criteria={
                        criterion["name"] for criterion in evaluation["testing_criteria"]
                    },
                    report_path=args.report,
                )


def ensure_evaluator(project: AIProjectClient, filename: str, name: str) -> None:
    for evaluator in project.beta.evaluators.list(type="custom"):
        if evaluator.name == name:
            print(f"Using evaluator: {name}:{evaluator.version}", flush=True)
            return

    definition = json.loads((Path(__file__).parent / filename).read_text())
    if definition.pop("name") != name:
        raise ValueError(f"Evaluator name in {filename} does not match {name!r}")
    evaluator = project.beta.evaluators.create_version(name, evaluator_version=definition)
    print(f"Created evaluator: {name}:{evaluator.version}", flush=True)


def wait_for_evaluation(
    client: OpenAI,
    eval_id: str,
    run_id: str,
    *,
    expected_rows: int,
    expected_criteria: set[str],
    report_path: Path | None,
) -> None:
    deadline = time.monotonic() + 3600
    run = client.evals.runs.retrieve(run_id, eval_id=eval_id)
    while run.status in ("queued", "in_progress"):
        report = {
            "eval_id": eval_id,
            "run_id": run_id,
            "status": run.status,
            "results_complete": False,
        }
        if report_path:
            report_path.write_text(json.dumps(report, indent=2) + "\n")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Evaluation {run_id} did not finish within 60 minutes; it may still be running."
            )
        print(f"Waiting for evaluation: {run.status}", flush=True)
        time.sleep(30)
        run = client.evals.runs.retrieve(run_id, eval_id=eval_id)

    report = {
        "eval_id": eval_id,
        "run_id": run_id,
        "status": run.status,
        "results_complete": False,
        "report_url": run.report_url,
        "result_counts": run.result_counts.model_dump(),
    }
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    if run.status != "completed":
        raise RuntimeError(f"Evaluation {run_id} ended with status {run.status}: {run.error}")
    counts = run.result_counts
    if (
        run.error is not None
        or counts.passed is None
        or counts.failed is None
        or counts.errored != 0
        or counts.total != expected_rows
        or counts.passed + counts.failed != expected_rows
        or counts.model_dump().get("skipped") not in (None, 0)
    ):
        raise RuntimeError(
            f"Evaluation {run_id} has errors, skipped rows or incomplete results: {counts}"
        )
    for criterion in run.per_testing_criteria_results:
        result = criterion.model_dump()
        if result.get("errored") not in (None, 0) or result.get("skipped") not in (None, 0):
            raise RuntimeError(f"Evaluator {criterion.testing_criteria} has errors or skipped rows")

    scores: dict[str, list[float]] = {name: [] for name in expected_criteria}
    passes = dict.fromkeys(expected_criteria, 0)
    items = list(client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=100))
    if len(items) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} evaluation rows, received {len(items)}")
    for item in items:
        if item.status != "completed" or item.sample.error is not None:
            raise RuntimeError(f"Evaluation row {item.id} is not complete or has a sample error")
        results = item.model_dump(warnings=False)["results"]
        if (
            len(results) != len(expected_criteria)
            or {r.get("name") for r in results} != expected_criteria
        ):
            raise RuntimeError(f"Evaluation row {item.id} is missing evaluator results")
        for result in results:
            score = result.get("score")
            passed = result.get("passed")
            if (
                result.get("status") not in (None, "completed")
                or result.get("error") is not None
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not isfinite(score)
                or not isinstance(passed, bool)
            ):
                raise RuntimeError(f"Evaluation row {item.id} has an invalid score or pass result")
            scores[result["name"]].append(score)
            passes[result["name"]] += int(passed)

    report["criteria"] = [
        {
            "name": name,
            "mean_score": fmean(scores[name]),
            "passed": passes[name],
            "failed": expected_rows - passes[name],
            "total": expected_rows,
        }
        for name in sorted(expected_criteria)
    ]
    report["results_complete"] = True
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
