import json
from unittest.mock import Mock

import main
import pytest
from agent_framework import ChatResponse, ChatResponseUpdate, Content, ResponseStream
from conftest import inline_config
from starlette.testclient import TestClient

TEST_ANSWER = "TEST DOUBLE: not a real model answer or evaluation result."


@pytest.fixture
def build_host(monkeypatch):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://invalid.example/api/projects/test")
    monkeypatch.setattr(main.ResponsesHostServer, "run", lambda self: None)
    constructor = Mock(wraps=main.ResponsesHostServer)
    monkeypatch.setattr(main, "ResponsesHostServer", constructor)

    def build():
        main.main()
        return constructor.call_args.args[0]

    return build


@pytest.fixture
def model_calls(monkeypatch):
    calls = []

    def respond(self, *, messages, options, stream=False, **kwargs):
        calls.append((list(messages), dict(options)))

        async def updates():
            if len(calls) == 1:
                contents = [
                    Content.from_function_call(
                        f"call_{i}", name, arguments=json.dumps({"query": query})
                    )
                    for i, (name, query) in enumerate(
                        [
                            ("search_policies", "purchasing training software"),
                            ("search_workplace_notices", "Nova"),
                        ]
                    )
                ]
            else:
                contents = [Content.from_text(TEST_ANSWER)]
            yield ChatResponseUpdate(
                role="assistant",
                contents=contents,
                response_id=f"resp_{len(calls)}",
                message_id=f"msg_{len(calls)}",
            )

        return ResponseStream(updates(), finalizer=ChatResponse.from_updates)

    monkeypatch.setattr(main.FoundryChatClient, "_inner_get_response", respond)
    return calls


def test_candidate_configures_the_framework_agent(monkeypatch, config, build_host):
    config.tool_definitions[0]["function"]["description"] = "Candidate policy description"
    monkeypatch.setenv(
        "OPTIMIZATION_CONFIG",
        inline_config(
            config, instructions="Candidate instructions", model="candidate", temperature=0.4
        ),
    )
    agent = build_host()
    assert agent.default_options["instructions"] == (
        "Candidate instructions\n\nScenario reference date (UTC): 2026-10-05."
    )
    assert agent.client.model == "candidate"
    assert agent.default_options["temperature"] == 0.4
    assert agent.default_options["store"] is False
    assert agent.default_options["reasoning"] == {"effort": "low"}
    assert agent.default_options["tools"][0].description == "Candidate policy description"


@pytest.mark.parametrize("stream", [False, True])
def test_framework_host_executes_tools_and_returns_answer(monkeypatch, model_calls, stream):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://invalid.example/api/projects/test")

    def run(host):
        with TestClient(host) as http:
            response = http.post(
                "/responses",
                json={
                    "input": "Can I buy Nova Learning licences for our new graduates?",
                    "stream": stream,
                },
            )
        assert response.status_code == 200, response.text
        if stream:
            assert "response.output_text.delta" in response.text
            assert "response.completed" in response.text
            assert TEST_ANSWER in response.text
        else:
            body = response.json()
            assert body["status"] == "completed"
            assert any(
                content.get("text") == TEST_ANSWER
                for item in body["output"]
                for content in item.get("content", [])
            )

    monkeypatch.setattr(main.ResponsesHostServer, "run", run)
    main.main()
    assert len(model_calls) == 2
    results = [
        content
        for message in model_calls[1][0]
        for content in message.contents
        if content.type == "function_result"
    ]
    assert len(results) == 2
    documents = [
        document for content in results for document in json.loads(content.result)["documents"]
    ]
    assert {document["id"] for document in documents} == {
        "policy:purchasing",
        "policy:training-suitability",
        "policy:software-review",
        "notice:nova-graduate-exception",
        "notice:nova-portal-clearance",
    }
    assert model_calls[0][1]["instructions"].endswith("Scenario reference date (UTC): 2026-10-05.")
    notice = next(d for d in documents if d["id"] == "notice:nova-graduate-exception")
    assert notice["issued"] == "2026-10-04"
    assert "November 4, 2026 inclusive" in notice["content"]
    assert model_calls[0][1]["store"] is False
    assert all(options["reasoning"] == {"effort": "low"} for _, options in model_calls)


def test_missing_endpoint_fails_before_starting_host(monkeypatch):
    host = Mock()
    monkeypatch.setattr(main, "ResponsesHostServer", host)
    with pytest.raises(KeyError, match="FOUNDRY_PROJECT_ENDPOINT"):
        main.main()
    host.assert_not_called()


def test_framework_host_preserves_follow_up_history(monkeypatch, model_calls):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://invalid.example/api/projects/test")

    def run(host):
        with TestClient(host) as http:
            first = http.post("/responses", json={"input": "Initial question"})
            assert first.status_code == 200, first.text
            second = http.post(
                "/responses",
                json={"input": "Follow-up question", "previous_response_id": first.json()["id"]},
            )
            assert second.status_code == 200, second.text
            assert second.json()["status"] == "completed"

    monkeypatch.setattr(main.ResponsesHostServer, "run", run)
    main.main()
    texts = [content.text for message in model_calls[-1][0] for content in message.contents]
    assert texts.count("Initial question") == 1
    assert texts.count(TEST_ANSWER) == 1
    assert texts.count("Follow-up question") == 1


def test_model_failure_is_not_a_successful_answer(monkeypatch):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://invalid.example/api/projects/test")

    def fail(*args, **kwargs):
        raise RuntimeError("Deliberate model failure")

    def run(host):
        with TestClient(host) as http:
            response = http.post("/responses", json={"input": "Question"})
        assert response.status_code >= 400 or response.json()["status"] == "failed"

    monkeypatch.setattr(main.FoundryChatClient, "_inner_get_response", fail)
    monkeypatch.setattr(main.ResponsesHostServer, "run", run)
    main.main()
