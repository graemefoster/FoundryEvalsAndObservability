import json
import re
import shutil
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import tools
import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import EvaluatorVersion, PromptBasedEvaluatorDefinition
from conftest import ROOT

import evaluate


def next_action_requests(*, release=False, smoke=False):
    return evaluate.prepare_requests(
        ROOT
        / "agent/datasets/next-action"
        / ("golden-holdout.jsonl" if release else "golden-development.jsonl"),
        agent_version="1",
        judge_model="gpt-5.5",
        smoke=smoke,
    )


@pytest.mark.parametrize("release,count", [(False, 16), (True, 12)])
def test_single_binary_objective_and_question_only_agent_input(release, count):
    requests = next_action_requests(release=release)
    assert "rubric" not in requests
    assert len(requests["evaluation"]["testing_criteria"]) == 1
    criterion = requests["evaluation"]["testing_criteria"][0]
    assert criterion["name"] == "next_action_success"
    assert criterion["evaluator_name"] == "purchasing-next-action"
    assert criterion["initialization_parameters"] == {"deployment_name": "gpt-5.5", "threshold": 1}
    assert criterion["data_mapping"] == {
        "query": "{{item.query}}",
        "ground_truth": "{{item.ground_truth}}",
        "response": "{{sample.output_text}}",
    }
    definition = EvaluatorVersion(requests["evaluator"]).definition
    assert isinstance(definition, PromptBasedEvaluatorDefinition)
    assert definition.as_dict()["metrics"]["custom_prompt"] == {
        "type": "ordinal",
        "desirable_direction": "increase",
        "min_value": 0,
        "max_value": 1,
    }
    source = requests["run"]["data_source"]
    assert len(source["source"]["content"]) == count
    assert source["target"] == {
        "type": "azure_ai_agent",
        "name": "purchasing-advice-demo",
        "version": "1",
    }
    assert source["input_messages"]["template"] == [
        {
            "type": "message",
            "role": "user",
            "content": {"type": "input_text", "text": "{{item.query}}"},
        }
    ]
    filename = "golden-holdout.jsonl" if release else "golden-development.jsonl"
    expected = [
        json.loads(line)
        for line in (ROOT / "agent/datasets/next-action" / filename).read_text().splitlines()
    ]
    assert [entry["item"] for entry in source["source"]["content"]] == expected


def test_datasets_are_balanced_disjoint_and_source_referenced():
    source_ids = {
        doc["id"]
        for filename in ("policies.json", "notices.json")
        for doc in tools.read_documents(filename)
    }
    names, queries = set(), set()
    for release, per_group in [(False, 4), (True, 3)]:
        rows = next_action_requests(release=release)["run"]["data_source"]["source"]["content"]
        assert Counter(row["item"]["name"].split("_")[0] for row in rows) == {
            "clarify": per_group,
            "remaining": per_group,
            "exception": per_group,
            "ready": per_group,
        }
        for entry in rows:
            row = entry["item"]
            assert set(row) == {"name", "query", "ground_truth"}
            assert row["name"] not in names and row["query"] not in queries
            names.add(row["name"])
            queries.add(row["query"])
            match = re.match(r"Decision date: (\d{4}-\d{2}-\d{2})\. ", row["query"])
            assert match and date.fromisoformat(match[1]).isoformat() == match[1]
            citations = set(re.findall(r"(?:policy|notice):[a-z-]+", row["ground_truth"]))
            assert citations and citations <= source_ids
    smoke = next_action_requests(smoke=True)["run"]["data_source"]["source"]["content"]
    assert {row["item"]["name"].split("_")[0] for row in smoke} == {
        "clarify",
        "remaining",
        "exception",
        "ready",
    }


def test_native_sdk_accepts_request_shapes_offline():
    requests = next_action_requests()
    sent = []

    def respond(request):
        body = json.loads(request.content)
        sent.append(body)
        if request.url.path.endswith("/runs"):
            return httpx.Response(
                200,
                json={
                    "id": "run_test",
                    "object": "eval.run",
                    "eval_id": "eval_test",
                    "status": "queued",
                    "created_at": 0,
                    **body,
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "eval_test",
                "object": "eval",
                "created_at": 0,
                **body,
            },
        )

    with (
        AIProjectClient(
            endpoint="https://invalid.example/api/projects/test", credential=Mock()
        ) as project,
        project.get_openai_client(
            api_key="offline-test-only",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
            max_retries=0,
        ) as client,
    ):
        definition = client.evals.create(**requests["evaluation"])
        client.evals.runs.create(eval_id=definition.id, **requests["run"])
    assert sent == [requests["evaluation"], requests["run"]]


def test_optimizer_freezes_disjoint_training_validation_and_baseline(monkeypatch, tmp_path):
    requests = next_action_requests()
    validation = next_action_requests(release=True)["run"]["data_source"]["source"]["content"]
    shutil.copy2(ROOT / "optimize-next-action.yaml", tmp_path)
    shutil.copytree(
        ROOT / "agent/.agent_configs/baseline", tmp_path / "agent/.agent_configs/baseline"
    )
    shutil.copytree(ROOT / "agent/datasets", tmp_path / "agent/datasets")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    project = Mock()
    project.beta.evaluators.create_version.return_value.version = "9"
    prepared = evaluate.prepare_optimizer(project, requests)
    config = prepared["config"]
    assert len(config["evaluators"]) == 1
    assert config["evaluators"][0] == {
        "name": "purchasing-next-action",
        "version": "9",
        "initialization_parameters": {"deployment_name": "gpt-5.5", "threshold": 1},
    }
    assert config["options"] == {
        "eval_model": "gpt-5.5",
        "optimization_model": "gpt-5.5",
        "max_candidates": 2,
    }
    validation_path = Path(config["validation_dataset"]["local_uri"])
    assert validation_path.is_relative_to(tmp_path / "evidence")
    assert validation_path != Path(config["dataset"]["local_uri"])
    assert len(prepared["validation_dataset"]) == 12
    assert prepared["validation_dataset"] == [row["item"] for row in validation]
    assert [json.loads(line) for line in validation_path.read_text().splitlines()] == prepared[
        "validation_dataset"
    ]
    for field in ("name", "query"):
        assert not {row[field] for row in prepared["dataset"]} & {
            row[field] for row in prepared["validation_dataset"]
        }
    assert len(prepared["dataset"]) == 16
    assert prepared["dataset"] == [
        row["item"] for row in requests["run"]["data_source"]["source"]["content"]
    ]
    baseline = Path(config["agent"]["config"])
    assert baseline.is_relative_to(tmp_path / "evidence")
    for filename in ("metadata.yaml", "instructions.md", "tools.json"):
        assert (baseline.parent / filename).read_bytes() == (
            ROOT / "agent/.agent_configs/baseline" / filename
        ).read_bytes()
    assert yaml.safe_load(baseline.read_text())["model"] == "gpt-5.4-mini"
    project.beta.agents.begin_create_optimization_job.assert_not_called()


@pytest.mark.parametrize("damage", ["empty", "missing_reference", "duplicate", "name", "query"])
def test_optimizer_rejects_invalid_or_overlapping_holdout(monkeypatch, tmp_path, damage):
    requests = next_action_requests()
    validation = [
        row["item"]
        for row in next_action_requests(release=True)["run"]["data_source"]["source"]["content"]
    ]
    if damage == "empty":
        validation = []
    elif damage == "missing_reference":
        del validation[0]["ground_truth"]
    elif damage == "duplicate":
        validation.append(deepcopy(validation[0]))
    else:
        validation[0][damage] = requests["run"]["data_source"]["source"]["content"][0]["item"][
            damage
        ]
    shutil.copy2(ROOT / "optimize-next-action.yaml", tmp_path)
    directory = tmp_path / "agent/datasets/next-action"
    directory.mkdir(parents=True)
    (directory / "golden-holdout.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in validation)
    )
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    project = Mock()
    with pytest.raises(ValueError, match="Holdout"):
        evaluate.prepare_optimizer(project, requests)
    project.beta.evaluators.create_version.assert_not_called()


@pytest.mark.parametrize("kind", ["release", "smoke"])
def test_optimizer_rejects_non_development_inputs(monkeypatch, tmp_path, kind):
    requests = next_action_requests(release=kind == "release", smoke=kind == "smoke")
    shutil.copy2(ROOT / "optimize-next-action.yaml", tmp_path)
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    project = Mock()
    with pytest.raises(ValueError, match="full development set only"):
        evaluate.prepare_optimizer(project, requests)
    project.beta.evaluators.create_version.assert_not_called()


def test_dry_run_does_not_need_credentials_or_endpoint(monkeypatch, tmp_path):
    shutil.copytree(ROOT / "evaluators", tmp_path / "evaluators")
    shutil.copytree(ROOT / "agent/datasets/next-action", tmp_path / "agent/datasets/next-action")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    project = Mock(side_effect=AssertionError("Must not open a cloud client"))
    monkeypatch.setattr(evaluate, "AIProjectClient", project)
    monkeypatch.setattr("sys.argv", ["evaluate.py", "--dry-run"])
    evaluate.main()
    snapshots = list((tmp_path / "evidence").glob("evaluation-*.json"))
    assert len(snapshots) == 1
    snapshot = json.loads(snapshots[0].read_text())
    assert snapshot["run"]["data_source"]["type"] == "azure_ai_target_completions"
    assert len(snapshot["run"]["data_source"]["source"]["content"]) == 16
    project.assert_not_called()


def test_cli_submits_hosted_agent_run_with_metadata(monkeypatch, tmp_path):
    shutil.copytree(ROOT / "evaluators", tmp_path / "evaluators")
    shutil.copytree(ROOT / "agent/datasets/next-action", tmp_path / "agent/datasets/next-action")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://invalid.example/api/projects/test")
    monkeypatch.setattr("sys.argv", ["evaluate.py"])
    project_context = Mock()
    project = Mock()
    project_context.__enter__ = Mock(return_value=project)
    project_context.__exit__ = Mock(return_value=False)
    client_context = Mock()
    client = Mock()
    client_context.__enter__ = Mock(return_value=client)
    client_context.__exit__ = Mock(return_value=False)
    project.get_openai_client.return_value = client_context
    project.beta.evaluators.create_version.return_value.version = "3"
    client.evals.create.return_value.id = "eval_test"
    client.evals.runs.create.return_value.id = "run_test"
    client.evals.runs.create.return_value.report_url = None
    monkeypatch.setattr(evaluate, "AIProjectClient", Mock(return_value=project_context))
    evaluate.main()
    run = client.evals.runs.create.call_args.kwargs
    assert run["eval_id"] == "eval_test"
    assert run["metadata"]["dataset_split"] == "development"
    assert run["metadata"]["agent_version"] == "1"
    assert run["data_source"]["type"] == "azure_ai_target_completions"
    assert run["data_source"]["target"] == {
        "type": "azure_ai_agent",
        "name": "purchasing-advice-demo",
        "version": "1",
    }
    assert len(run["data_source"]["source"]["content"]) == 16
    snapshot = json.loads(next((tmp_path / "evidence").glob("evaluation-*.json")).read_text())
    assert snapshot["run_id"] == "run_test"
    assert snapshot["eval_id"] == "eval_test"


def test_optimizer_preparation_rejects_unverified_judge_set(monkeypatch, tmp_path):
    requests = next_action_requests()
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    (tmp_path / "optimize-next-action.yaml").write_text(
        "evaluators:\n  - name: builtin.task_adherence\n"
    )
    project = Mock()
    with pytest.raises(ValueError, match="single next-action judge"):
        evaluate.prepare_optimizer(project, requests)
    project.beta.evaluators.create_version.assert_not_called()


def test_show_saves_original_service_status_and_errors(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    client = Mock()
    raw = {
        "status": "failed",
        "result_counts": {"total": 1, "errored": 1, "passed": 0},
        "error": {"message": "Deliberate service failure"},
        "data_source": {"type": "azure_ai_target_completions"},
    }
    client.evals.runs.with_raw_response.retrieve.return_value.http_response.json.return_value = raw
    client.evals.with_raw_response.retrieve.return_value.http_response.json.return_value = {
        "id": "eval_test"
    }
    client.evals.runs.output_items.list.return_value = []
    report = evaluate.show_results(client, "eval_test", "evalrun_test")
    assert report["run"] == raw
    assert json.loads((tmp_path / "evidence/evalrun_test.json").read_text()) == report
    assert "Deliberate service failure" in capsys.readouterr().out
    client.evals.create.assert_not_called()
    client.evals.runs.create.assert_not_called()
