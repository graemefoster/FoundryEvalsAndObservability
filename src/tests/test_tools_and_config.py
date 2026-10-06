import json
import shutil
from datetime import date

import pytest
import tools
from configuration import CONFIG_DIR, read_config
from conftest import inline_config
from tools import read_documents, search_policies, search_workplace_notices


@pytest.mark.parametrize("filename,count", [("policies.json", 3), ("notices.json", 5)])
def test_corpus_contains_citable_fixed_snapshot_evidence(filename, count):
    documents = read_documents(filename)
    assert len(documents) == count
    assert tools.REFERENCE_DATE == date(2026, 10, 5)
    for document in documents:
        assert document["synthetic"] is True
        assert document["id"] and document["title"] and document["content"]
        assert date.fromisoformat(document["issued"]) <= tools.REFERENCE_DATE
        assert "{{" not in json.dumps(document)


@pytest.mark.parametrize(
    "search,query,expected",
    [
        (search_policies, "purchasing", {"policy:purchasing"}),
        (search_policies, "software security", {"policy:software-review"}),
        (
            search_policies,
            "training online purchasing",
            {"policy:purchasing", "policy:software-review", "policy:training-suitability"},
        ),
        (
            search_workplace_notices,
            "Nova Learning",
            {"notice:nova-graduate-exception", "notice:nova-portal-clearance"},
        ),
        (
            search_workplace_notices,
            "DesignCloud",
            {"notice:designcloud-public-clearance", "notice:designcloud-customer-pilot"},
        ),
        (search_workplace_notices, "BrightPath", {"notice:brightpath-leadership-exception"}),
    ],
)
def test_focused_search_finds_combined_and_contrasting_sources(search, query, expected):
    result = json.loads(search(query))
    assert result["query"] == query
    assert 1 <= len(result["documents"]) <= 3
    assert expected <= {document["id"] for document in result["documents"]}
    assert search(query) == search(query)


def test_search_reads_document_content_not_dataset_or_supplier_routing(monkeypatch, tmp_path):
    document = {"id": "unseen", "title": "New notice", "content": "Quokka renewals are reviewed."}
    (tmp_path / "notices.json").write_text(json.dumps([document]))
    monkeypatch.setattr(tools, "DATA", tmp_path)
    assert json.loads(search_workplace_notices("QUOKKA renewal"))["documents"] == [document]
    assert json.loads(search_workplace_notices("Nova"))["documents"] == []


@pytest.mark.parametrize("query", ["", "  ", "the and to", "***"])
def test_empty_search_is_an_explicit_error(query):
    with pytest.raises(ValueError, match="searchable words"):
        search_policies(query)


def test_unknown_supplier_is_no_match_not_invented_clearance():
    assert json.loads(search_workplace_notices("TaskNest"))["documents"] == []


def test_unavailable_source_is_not_an_empty_success(monkeypatch, tmp_path):
    monkeypatch.setattr("tools.DATA", tmp_path)
    with pytest.raises(FileNotFoundError):
        search_policies("purchasing")


def test_corrupt_source_is_not_an_empty_success(monkeypatch, tmp_path):
    (tmp_path / "policies.json").write_text("{broken")
    monkeypatch.setattr(tools, "DATA", tmp_path)
    with pytest.raises(json.JSONDecodeError):
        search_policies("purchasing")


def test_baseline_loads_from_another_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = read_config()
    assert config.model == "gpt-5.4-mini"
    assert "decision date" in config.instructions
    assert {item["function"]["name"] for item in config.tool_definitions} == {
        "search_policies",
        "search_workplace_notices",
    }


def test_inline_candidate_changes_instructions_model_and_tool_description(monkeypatch, config):
    config.tool_definitions[0]["function"]["description"] = "Candidate tool description"
    monkeypatch.setenv(
        "OPTIMIZATION_CONFIG",
        inline_config(config, instructions="Candidate instructions", model="candidate-model"),
    )
    candidate = read_config()
    assert candidate.instructions == "Candidate instructions"
    assert candidate.model == "candidate-model"
    assert candidate.tool_definitions[0]["function"]["description"] == "Candidate tool description"


def test_local_candidate_selection(monkeypatch, tmp_path):
    shutil.copytree(CONFIG_DIR / "baseline", tmp_path / "candidate-one")
    (tmp_path / "candidate-one" / "instructions.md").write_text("Local candidate instructions.")
    monkeypatch.setenv("OPTIMIZATION_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("OPTIMIZATION_CANDIDATE_ID", "candidate-one")
    assert read_config().instructions == "Local candidate instructions."


def test_unknown_candidate_cannot_silently_use_baseline(monkeypatch):
    monkeypatch.setenv("OPTIMIZATION_CANDIDATE_ID", "missing")
    with pytest.raises(ValueError, match="not present"):
        read_config()


def test_failed_remote_candidate_cannot_use_baseline(monkeypatch, config):
    monkeypatch.setenv("OPTIMIZATION_CANDIDATE_ID", "remote")
    monkeypatch.setenv("OPTIMIZATION_RESOLVE_ENDPOINT", "https://invalid.example")
    monkeypatch.setattr("configuration.load_config", lambda **kwargs: config)
    with pytest.raises(ValueError, match="refusing baseline fallback"):
        read_config()


def test_missing_configuration_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("OPTIMIZATION_LOCAL_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="nonempty"):
        read_config()


@pytest.mark.parametrize("value", ["{broken", '{"instructions": ""}'])
def test_invalid_inline_configuration_fails(monkeypatch, value):
    monkeypatch.setenv("OPTIMIZATION_CONFIG", value)
    with pytest.raises(ValueError):
        read_config()
