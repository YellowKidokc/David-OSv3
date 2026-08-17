from fastapi.testclient import TestClient


def test_openai_compat_models_and_chat_completion(tmp_path, monkeypatch):
    from hub.api import routes_openai_compat
    from hub.api.app import create_app
    from hub.services import provider_router

    routes_openai_compat.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(provider_router, "PROVIDERS_PATH", tmp_path / "providers.json")
    provider_router.reload_registry()
    client = TestClient(create_app())

    models = client.get("/v1/models")
    completion = client.post(
        "/v1/chat/completions",
        json={
            "model": "top-of-mind-router",
            "messages": [{"role": "user", "content": "hello from Mattermost"}],
        },
    )

    assert models.status_code == 200
    assert models.json()["data"][0]["id"] == "top-of-mind-router"
    assert completion.status_code == 200
    body = completion.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert "Top of Mind router is online" in body["choices"][0]["message"]["content"]
    assert body["top_of_mind"]["request_message_id"]


def test_openai_compat_responses_endpoint(tmp_path):
    from hub.api import routes_openai_compat
    from hub.api.app import create_app

    routes_openai_compat.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    client = TestClient(create_app())

    response = client.post(
        "/v1/responses",
        json={
            "model": "top-of-mind-router",
            "input": "route this through the AI crew",
            "instructions": "Be concise.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["status"] == "completed"
    assert body["output_text"]
    assert body["output"][0]["content"][0]["text"] == body["output_text"]


def test_openai_compat_uses_deepseek_when_key_is_configured(tmp_path, monkeypatch):
    from hub.api import routes_openai_compat
    from hub.api.app import create_app

    routes_openai_compat.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(routes_openai_compat, "_call_deepseek", lambda messages: "DeepSeek downstream reply")
    client = TestClient(create_app())

    completion = client.post(
        "/v1/chat/completions",
        json={
            "model": "top-of-mind-router",
            "messages": [{"role": "user", "content": "use downstream"}],
        },
    )

    assert completion.status_code == 200
    body = completion.json()
    assert body["choices"][0]["message"]["content"] == "DeepSeek downstream reply"
    assert body["top_of_mind"]["provider"] == "deepseek"


def test_openai_compat_routes_prefixed_prompt_to_persona(tmp_path, monkeypatch):
    from hub.api import routes_openai_compat
    from hub.api.app import create_app

    captured = {}

    def fake_deepseek(messages):
        captured["messages"] = [message.model_dump() for message in messages]
        return "Codex routed reply"

    routes_openai_compat.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(routes_openai_compat, "_call_deepseek", fake_deepseek)
    client = TestClient(create_app())

    personas = client.get("/v1/top-of-mind/personas")
    completion = client.post(
        "/v1/chat/completions",
        json={
            "model": "top-of-mind-router",
            "messages": [{"role": "user", "content": "/codex fix the route"}],
        },
    )

    assert personas.status_code == 200
    assert any(item["id"] == "codex" for item in personas.json()["data"])
    assert completion.status_code == 200
    body = completion.json()
    assert body["top_of_mind"]["persona"] == "codex"
    assert body["top_of_mind"]["route_reason"].startswith("prompt-prefix:")
    assert "You are Codex" in captured["messages"][0]["content"]
    assert captured["messages"][-1]["content"] == "fix the route"
