from hub.storage.db import Database
from hub.storage.desktop_file_cache_repo import DesktopFileCacheRepo


def test_desktop_file_cache_upsert_and_search(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = DesktopFileCacheRepo(db.conn)

    cached = repo.upsert_file(
        full_path=r"C:\Users\David\Desktop\Top Mind Notes.md",
        tier="desktop",
        owner_id="david",
        size_bytes=123,
        tags=["prompt", "notes"],
    )
    results = repo.search("Top Mind", owner_id="david")

    assert cached["filename"] == "Top Mind Notes.md"
    assert cached["extension"] == ".md"
    assert results[0]["full_path"] == r"C:\Users\David\Desktop\Top Mind Notes.md"


def test_file_cache_http_routes(tmp_path):
    from fastapi.testclient import TestClient

    from hub.api import routes_file_cache
    from hub.api.app import create_app

    routes_file_cache.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    client = TestClient(create_app())

    create_response = client.post(
        "/files/cache",
        json={"full_path": r"C:\Users\David\Desktop\clip.txt", "owner_id": "codex", "tags": ["clipboard"]},
    )
    search_response = client.get("/files/cache/search", params={"q": "clip", "owner_id": "codex"})

    assert create_response.status_code == 200
    assert search_response.status_code == 200
    assert search_response.json()["files"][0]["filename"] == "clip.txt"
