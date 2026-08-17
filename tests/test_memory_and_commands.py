from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.storage.memory_repo import MemoryRepo
from hub.workers.runner import WorkerRunner


def test_top_cli_adds_embeds_and_searches_memory(tmp_path, capsys):
    from hub.cli import top_main

    db_path = tmp_path / "hub.sqlite3"
    top_main(["--db", str(db_path), "memory-add", "--title", "Vector plan", "--body", "Embeddings connect memory to prompts.", "--tag", "vectors", "--embed"])
    top_main(["--db", str(db_path), "memory-search", "memory prompts", "--mode", "vector"])
    output = capsys.readouterr().out

    assert "Vector plan" in output
    assert "vectors" in output


def test_memory_items_can_be_stored_and_searched(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = MemoryRepo(db.conn)

    item = repo.create_item(
        title="NAS plan",
        body="Use the NAS as a storage integration and keep secrets in secret refs.",
        source="codex",
        folder="Architecture",
        tags=["nas", "security"],
    )
    results = repo.search("NAS secrets")

    assert item["tags"] == ["nas", "security"]
    assert results[0]["id"] == item["id"]
    assert results[0]["score"] >= 2


def test_memory_items_can_be_embedded_and_vector_searched(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = MemoryRepo(db.conn)
    repo.create_item(title="Clipboard memory", body="Clipboard snippets should become searchable memory.")

    embedded = repo.embed_pending()
    results = repo.vector_search("searchable clipboard")

    assert embedded[0]["embedding"]
    assert results[0]["title"] == "Clipboard memory"


def test_command_line_job_captures_output(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    repo.create_job("command_line", {"command": ["py", "-3.12", "-c", "print('hello command')"], "timeout_seconds": 30})

    processed = WorkerRunner(repo).run_once(limit=1)[0]

    assert processed["status"] == "completed"
    assert processed["result"]["returncode"] == 0
    assert "hello command" in processed["result"]["stdout"]


def test_memory_and_command_http_routes(tmp_path):
    from fastapi.testclient import TestClient

    from hub.api import routes_commands, routes_memory
    from hub.api.app import create_app

    db_path = tmp_path / "hub.sqlite3"
    routes_commands.DEFAULT_DB_PATH = db_path
    routes_memory.DEFAULT_DB_PATH = db_path
    client = TestClient(create_app())

    memory_response = client.post(
        "/memory/items",
        json={"title": "Prompt rule", "body": "Keep API prompts in folders.", "tags": ["prompts"]},
    )
    embed_response = client.post("/memory/embed-pending")
    command_response = client.post(
        "/operator/commands",
        json={"command": ["py", "-3.12", "-c", "print('queued')"], "review_required": True},
    )

    assert memory_response.status_code == 200
    assert embed_response.status_code == 200
    assert command_response.status_code == 200
    assert command_response.json()["job"]["status"] == "waiting_review"
