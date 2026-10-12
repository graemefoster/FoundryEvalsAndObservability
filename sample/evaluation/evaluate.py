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
# EVAL_DATASET lets CI run the drift set (or any other JSONL) through the same judges.
DATASET = Path(
    os.environ.get(
        "EVAL_DATASET", Path(__file__).resolve().parent / "datasets/approvers-development.jsonl"
    )
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the hosted demo agent (billable).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print requests; no cloud calls.")
    mode.add_argument(
        "--register-only", action="store_true", help="Ensure evaluators exist; no scoring run."
    )
    parser.add_argument(
        "--update-evaluators",
        action="store_true",
        help="Register the local evaluator JSON as a new version before running.",
    )
    parser.add_argument(
        "--wait", action="store_true", help="Wait for results; fail on execution errors."
    )
    parser.add_argument(
        "--report", type=Path, help="Write a score summary JSON file; requires --wait."
    )
    parser.add_argument(
        "--max-unscored",
        type=int,
        default=1,
        help="Questions each judge may fail to score (e.g. a rate-limit error) before the run "
        "fails; they're left out of that judge's averages. Use 0 where every score matters.",
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
                AIProjectClient(endpoint=project_endpoint(), credential=credential)
            )
            update = args.update_evaluators
            ensure_evaluator(project, "purchasing-next-action.json", EVALUATOR_NAME, update)
            ensure_evaluator(project, "purchasing-demo-rubric.json", RUBRIC_NAME, update)
            if args.register_only:
                return

        # 2. Load the questions and references; the agent answers are generated during the run.
        # Keep only the fields the item schema allows; optimizer-only fields such as
        # "criteria" would otherwise fail validation.
        rows = [
            {key: row[key] for key in ("name", "query", "ground_truth")}
            for row in map(json.loads, filter(str.strip, DATASET.read_text().splitlines()))
        ]

        # 3. Define the evaluation and map its inputs.
        evaluation = {
            "name": f"purchasing-next-action-evaluation-{DATASET.stem}",
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
                    # The prompt judge sees the question, reference, actual answer and tool calls.
                    # The tool calls let its reason explain *why* an answer failed, which is
                    # what the optimiser's reflection model learns from.
                    "data_mapping": {
                        "query": "{{item.query}}",
                        "ground_truth": "{{item.ground_truth}}",
                        "response": "{{sample.output_text}}",
                        "tool_calls": "{{sample.tool_calls}}",
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
                    max_unscored=args.max_unscored,
                )


def project_endpoint() -> str:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint.startswith("https://"):
        raise SystemExit(
            "FOUNDRY_PROJECT_ENDPOINT is empty or not an https URL in this terminal.\n"
            "From sample/, run:\n"
            '  export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)"'
        )
    return endpoint


def ensure_evaluator(
    project: AIProjectClient, filename: str, name: str, update: bool = False
) -> None:
    if not update:
        for evaluator in project.beta.evaluators.list(type="custom"):
            if evaluator.name == name:
                print(f"Using evaluator: {name}:{evaluator.version}", flush=True)
                return

    definition = json.loads((Path(__file__).parent / filename).read_text())
    if definition.pop("name") != name:
        raise ValueError(f"Evaluator name in {filename} does not match {name!r}")
    evaluator = project.beta.evaluators.create_version(name, evaluator_version=definition)
    print(f"Registered evaluator: {name}:{evaluator.version}", flush=True)


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
                detail = result.get("error") or result.get("reason") or result.get("status")
                lines.append(f"  {question}: {str(detail)[:300]}")
    return lines


def wait_for_evaluation(
    client: OpenAI,
    eval_id: str,
    run_id: str,
    *,
    expected_rows: int,
    expected_criteria: set[str],
    report_path: Path | None,
    max_unscored: int = 0,
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
                f"{max_unscored}; see above. One-off errors are usually the judge model's rate "
                "limit: re-run."
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


if __name__ == "__main__":
    main()
