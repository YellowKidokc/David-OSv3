from hub.storage.db import Database
from hub.storage.top_of_mind_repo import TopOfMindRepo


def test_top_of_mind_http_message_flow(tmp_path):
    from fastapi.testclient import TestClient

    from hub.api import routes_top_of_mind
    from hub.api.app import create_app

    routes_top_of_mind.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    client = TestClient(create_app())

    source_response = client.post(
        "/top-of-mind/sources",
        json={"source_id": "kimi-cli", "label": "Kimi", "kind": "cli", "priority": 4},
    )
    message_response = client.post(
        "/top-of-mind/messages",
        json={"source_id": "kimi-cli", "body": "Checkpoint question", "wall": "wall-1", "folder": "Code"},
    )
    list_response = client.get("/top-of-mind/messages", params={"wall": "wall-1", "folder": "Code"})

    assert source_response.status_code == 200
    assert message_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()["messages"][0]["body"] == "Checkpoint question"


def test_top_of_mind_sources_messages_and_combine(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = TopOfMindRepo(db.conn)

    source = repo.upsert_source("kimi-cli", label="Kimi", kind="cli", priority=4)
    first = repo.post_message(source_id="kimi-cli", body="Question from Kimi", wall="wall-1", folder="Code")
    second = repo.post_message(source_id="codex", source_label="Codex", body="Answer from Codex", wall="wall-1", folder="Code")
    combined = repo.combine_messages([first["id"], second["id"]], wall="wall-1", folder="Code")
    stopped = repo.stop_all_sources()

    assert source["label"] == "Kimi"
    assert first["source_label"] == "Kimi"
    assert second["source_label"] == "Codex"
    assert combined["pinned"] is True
    assert combined["combined_from"] == [first["id"], second["id"]]
    assert "[Kimi] Question from Kimi" in combined["body"]
    assert "[Codex] Answer from Codex" in combined["body"]
    assert all(item["paused"] is True for item in stopped)


def test_top_of_mind_list_messages_defaults_to_newest_and_unarchived(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = TopOfMindRepo(db.conn)

    first = repo.post_message(source_id="clipboard", source_label="Clipboard", body="old")
    second = repo.post_message(source_id="clipboard", source_label="Clipboard", body="new")
    repo.set_message_state(first["id"], archived=True)

    messages = repo.list_messages(limit=75)
    archived = repo.list_messages(include_archived=True, limit=75)

    assert [message["id"] for message in messages] == [second["id"]]
    assert [message["id"] for message in archived] == [second["id"], first["id"]]


def test_api_action_registry_loads_groups_and_filters_actions():
    from hub.services.api_action_registry import get_api_action, list_api_actions

    path = "config/top_of_mind/api_actions.example.json"
    folders = list_api_actions(path, group="folders")
    action = get_api_action("folders.search", path)

    assert {item["id"] for item in folders["actions"]} == {"folders.search", "folders.tree", "folders.create"}
    assert action["endpoint"] == "/folders/search"
    assert action["result_card"]["type"] == "folder_list"


def test_api_action_registry_rejects_unsafe_endpoint(tmp_path):
    from hub.services.api_action_registry import ApiActionRegistryError, load_api_action_registry

    config = tmp_path / "bad_actions.json"
    config.write_text(
        '{"actions":[{"id":"bad","label":"Bad","method":"GET","endpoint":"../secrets"}]}',
        encoding="utf-8",
    )

    try:
        load_api_action_registry(config)
    except ApiActionRegistryError as exc:
        assert "safe absolute API path" in str(exc)
    else:
        raise AssertionError("expected unsafe endpoint to be rejected")
