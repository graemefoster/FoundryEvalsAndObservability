# Evaluate the agent's next action, not just whether it can quote a policy.
# This script submits the experiment. Foundry calls the agent and judges its answers.

import argparse
import json
import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# The agent answers the questions; a separate model acts as the judge.
# Versions identify the deployed agent and the marking rubric already stored in Foundry.
# A fresh project normally starts at version 1; use the actual setup/deployment results.
AGENT_NAME = "purchasing-advice-demo"
AGENT_VERSION = "2"
EVALUATOR_NAME = "purchasing-next-action"
EVALUATOR_VERSION = "1"
RUBRIC_NAME = "purchasing-demo-rubric"
RUBRIC_VERSION = "1"
JUDGE_MODEL = "gpt-5.5"
DATASET = Path(__file__).resolve().parent / "datasets/golden-development.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the hosted demo agent (billable).")
    parser.add_argument("--dry-run", action="store_true", help="Print requests; no cloud calls.")
    args = parser.parse_args()

    # 1. Load our 32 example situations and their expected next actions.
    # Each row has a case name, a question (query) and a reference answer (ground_truth).
    # There are no pre-recorded agent answers: those will be generated during the run.
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]

    # 2. Define the marking scheme and tell Foundry what fields our dataset contains.
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
                "name": "next_action_success",  # Label for this criterion in the results.
                "evaluator_name": EVALUATOR_NAME,  # Registered marking rubric.
                "evaluator_version": EVALUATOR_VERSION,  # Exact stored prompt evaluator.
                # Our existing rubric returns 1 for the correct next action, otherwise 0.
                "initialization_parameters": {
                    "deployment_name": JUDGE_MODEL,  # Model doing the marking, not the agent.
                    "threshold": 1,  # Only a score of 1 passes.
                },
                # The judge sees the question, the reference and the actual agent answer.
                # item.* comes from our dataset; sample.* comes from the live agent run.
                "data_mapping": {
                    "query": "{{item.query}}",
                    "ground_truth": "{{item.ground_truth}}",
                    "response": "{{sample.output_text}}",  # Newly generated agent answer.
                },
            },
            {
                "type": "azure_ai_evaluator",
                "name": "purchasing_behaviour",
                "evaluator_name": RUBRIC_NAME,
                "evaluator_version": RUBRIC_VERSION,
                "initialization_parameters": {"model": JUDGE_MODEL},
                # Native rubric scores behaviour without the reference answer.
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{sample.output_text}}",
                },
            },
        ],
    }
    # 3. Ask the deployed agent to answer each question, including using its own tools.
    # We target the whole agent, not a direct call to its underlying language model.
    data_source = {
        "type": "azure_ai_target_completions",  # Generate answers, then evaluate them.
        "source": {
            "type": "file_content",  # Send the rows inline; no separate dataset upload.
            "content": [{"item": row} for row in rows],
        },
        # Only the question reaches the agent. We never give it the reference answer.
        "input_messages": {
            "type": "template",  # Fill in the question separately for each case.
            "template": [
                {
                    "type": "message",
                    "role": "user",
                    "content": {"type": "input_text", "text": "{{item.query}}"},
                }
            ],
        },
        "target": {
            "type": "azure_ai_agent",  # Use the hosted agent, including its tools.
            "name": AGENT_NAME,
            "version": AGENT_VERSION,  # Evaluate this deployed version, not local code.
        },
    }
    # Safe rehearsal: show the request and stop before authentication or any cloud calls.
    if args.dry_run:
        print(json.dumps({"evaluation": evaluation, "data_source": data_source}, indent=2))
        return

    # 4. Connect to our Foundry project using Azure credentials.
    # get_openai_client() accesses the project's API, not the public OpenAI service.
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
        ) as project,
        project.get_openai_client() as client,
    ):
        # Save the evaluation definition. This does not yet ask the agent any questions.
        result = client.evals.create(**evaluation)
        print(f"Eval ID: {result.id}", flush=True)

        # 5. Start the billable run: Foundry generates answers and applies the judge.
        run = client.evals.runs.create(
            eval_id=result.id,
            name=evaluation["name"],
            data_source=data_source,
        )
        # Submission is not completion. Follow the report to see progress and results.
        print(f"Run ID: {run.id}")
        print(f"Status: {run.status}")
        if run.report_url:
            print(f"Report: {run.report_url}")
        print("View progress, answers and scores in Foundry Evaluations.")


if __name__ == "__main__":
    main()
