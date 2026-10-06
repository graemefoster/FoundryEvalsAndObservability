import json
from pathlib import Path

import httpx
import pytest
from configuration import read_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in (
        "OPTIMIZATION_CONFIG",
        "OPTIMIZATION_CANDIDATE_ID",
        "OPTIMIZATION_LOCAL_DIR",
        "OPTIMIZATION_RESOLVE_ENDPOINT",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_PROJECT_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AGENTSERVER_STATE_ROOT", str(tmp_path / "host-state"))
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("UV_OFFLINE", "true")

    def no_network(*args, **kwargs):
        raise AssertionError("Offline tests must not make network requests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)


@pytest.fixture
def config():
    return read_config()


def inline_config(config, **updates):
    data = {
        "instructions": config.instructions,
        "model": config.model,
        "tools": config.tool_definitions,
    }
    data.update(updates)
    return json.dumps(data)
