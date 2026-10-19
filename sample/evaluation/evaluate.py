# Evaluate the agent's next action, not just whether it can quote a policy.
# Foundry calls the deployed agent with each question, then judges its answers.
#
#   python evaluation/evaluate.py --dry-run    # print the requests; no cloud calls

import argparse
import json
import os
from contextlib import contextmanager
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from ci_report import check_baseline, wait_for_evaluation

HERE = Path(__file__).resolve().parent
AGENT_NAME = os.environ.get("AGENT_NAME", "purchasing-advice-demo")
JUDGE_MODEL = "gpt-5.5"
EVALUATOR_NAME = "purchasing-next-action"  # evaluation/purchasing-next-action.json
RUBRIC_NAME = "purchasing-demo-rubric"  # evaluation/purchasing-demo-rubric.json
# EVAL_DATASET lets CI run the holdout or drift set through the same judges.
DATASET = Path(os.environ.get("EVAL_DATASET", HERE / "datasets/approvers-development.jsonl"))


def main() -> None:
    args = parse_args()
    with connect(args.dry_run) as project:  # None for --dry-run
        # 1. Create the evaluators -> purchasing-next-action.json, purchasing-demo-rubric.json
        evaluators = create_evaluators(project, args.update_evaluators, args.register_only)
        if args.register_only:
            return

        # 2. Create the evaluation -> which judge sees which field
        evaluation = create_evaluation(project, evaluators)

        # 3. Create the dataset -> datasets/approvers-development.jsonl
        rows, data_source = create_dataset(DATASET)

        # 4. Run the evaluation -> Foundry calls the agent, then the judges
        run_evaluation(project, evaluation, rows, data_source, args)


def create_evaluators(project, update: bool, register: bool) -> dict[str, str] | None:
    """Register each judge from its JSON file, or reuse the matching registered version."""
    if project is None:
        return None
    return {
        name: ensure_evaluator(project, name, update=update, register=register)
        for name in (EVALUATOR_NAME, RUBRIC_NAME)
    }


def create_evaluation(project, evaluators: dict[str, str] | None) -> dict:
    """Define what each judge receives. Only the question goes to the agent (step 3)."""
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
            # Also make the agent's generated output available to the judges.
            "include_sample_schema": True,
        },
        "testing_criteria": [
            {
                # Binary judge: 1 for the correct next action, otherwise 0.
                "type": "azure_ai_evaluator",
                "name": "next_action_success",
                "evaluator_name": EVALUATOR_NAME,
                "initialization_parameters": {"deployment_name": JUDGE_MODEL, "threshold": 1},
                # Question, reference, answer and tool calls. The tool calls let its reason
                # explain *why* an answer failed, which the optimiser learns from.
                "data_mapping": {
                    "query": "{{item.query}}",
                    "ground_truth": "{{item.ground_truth}}",
                    "response": "{{sample.output_text}}",
                    "tool_calls": "{{sample.tool_calls}}",
                },
            },
            {
                # Rubric judge: scores behaviour without the reference answer.
                "type": "azure_ai_evaluator",
                "name": "purchasing_behaviour",
                "evaluator_name": RUBRIC_NAME,
                "initialization_parameters": {"model": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{sample.output_text}}",
                },
            },
        ],
    }
    if project is None:
        return evaluation

    # Pin the judge versions resolved in step 1.
    for criterion in evaluation["testing_criteria"]:
        criterion["evaluator_version"] = evaluators[criterion["evaluator_name"]]
    with project.get_openai_client() as client:
        evaluation["id"] = client.evals.create(**evaluation).id
    print(f"Eval ID: {evaluation['id']}", flush=True)
    return evaluation


def create_dataset(path: Path) -> tuple[list[dict], dict]:
    """Load the questions and references, and send only the question to the deployed agent."""
    # Keep only the fields the item schema allows; optimiser-only fields such as
    # "criteria" would otherwise fail validation.
    rows = [
        {key: row[key] for key in ("name", "query", "ground_truth")}
        for row in map(json.loads, filter(str.strip, path.read_text().splitlines()))
    ]
    data_source = {
        "type": "azure_ai_target_completions",
        "source": {"type": "file_content", "content": [{"item": row} for row in rows]},
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
        "target": {"type": "azure_ai_agent", "name": AGENT_NAME},
    }
    return rows, data_source


def run_evaluation(project, evaluation: dict, rows: list, data_source: dict, args) -> None:
    """Start the billable run. Submission is not completion: follow the report in Foundry."""
    if args.baseline:
        check_baseline(args.baseline, rows, evaluation)
    if project is None:
        print(json.dumps({"evaluation": evaluation, "data_source": data_source}, indent=2))
        return

    with project.get_openai_client() as client:
        run = client.evals.runs.create(
            eval_id=evaluation["id"], name=evaluation["name"], data_source=data_source
        )
        print(f"Run ID: {run.id}", flush=True)
        print(f"Status: {run.status}")
        if run.report_url:
            print(f"Report: {run.report_url}")
        print("View progress, answers and scores in Foundry Evaluations.")
        if args.wait:
            wait_for_evaluation(
                client,
                run.id,
                agent_name=AGENT_NAME,
                evaluation=evaluation,
                rows=rows,
                report_path=args.report,
                max_unscored=args.max_unscored,
            )


# --- Supporting code ---------------------------------------------------------


def ensure_evaluator(project: AIProjectClient, name: str, update: bool, register: bool) -> str:
    filename = f"{name}.json"
    definition = json.loads((HERE / filename).read_text())
    if definition.pop("name") != name:
        raise ValueError(f"Evaluator name in {filename} does not match {name!r}")
    if not update:
        for evaluator in project.beta.evaluators.list(type="custom"):
            if evaluator.name == name:
                registered = project.beta.evaluators.get_version(name, evaluator.version)
                if registered.definition.as_dict() != definition["definition"]:
                    raise ValueError(
                        f"Registered evaluator {name}:{evaluator.version} differs from {filename}. "
                        "Explicitly register the change with --update-evaluators --register-only, "
                        "then refresh the affected baselines."
                    )
                print(f"Using evaluator: {name}:{evaluator.version}", flush=True)
                return evaluator.version
        if not register:
            raise ValueError(
                f"No registered evaluator named {name}. Run --register-only before evaluating."
            )

    evaluator = project.beta.evaluators.create_version(name, evaluator_version=definition)
    print(f"Registered evaluator: {name}:{evaluator.version}", flush=True)
    return evaluator.version


@contextmanager
def connect(dry_run: bool):
    if dry_run:
        yield None
        return
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint.startswith("https://"):
        raise SystemExit(
            "FOUNDRY_PROJECT_ENDPOINT is empty or not an https URL in this terminal.\n"
            "From sample/, run:\n"
            '  export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)"'
        )
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
    ):
        yield project


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the hosted demo agent (billable).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print requests; no cloud calls.")
    mode.add_argument(
        "--register-only", action="store_true", help="Register missing evaluators; no scoring run."
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
        "--baseline", type=Path, help="Check dataset and judge compatibility before the run."
    )
    parser.add_argument(
        "--max-unscored",
        type=int,
        default=1,
        help="Questions each judge may fail to score (e.g. a rate-limit error) before the run "
        "fails; they're left out of that judge's averages. Use 0 where every score matters.",
    )
    args = parser.parse_args()
    if not AGENT_NAME.strip():
        parser.error("AGENT_NAME must not be empty")
    if args.wait and (args.dry_run or args.register_only):
        parser.error("--wait requires an evaluation run")
    if args.report and not args.wait:
        parser.error("--report requires --wait")
    if args.max_unscored < 0:
        parser.error("--max-unscored must be nonnegative")
    return args


if __name__ == "__main__":
    main()
