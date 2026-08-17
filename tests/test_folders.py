from hub.storage.db import Database
from hub.storage.folder_repo import FolderRepo


def test_folder_repo_creates_nested_folders_with_generated_codes(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = FolderRepo(db.conn)

    parent = repo.create_folder(name="Projects", owner_id="david")
    child = repo.create_folder(name="Lean Proofs", parent_id=parent["id"], owner_id="david", wall="framework", wall_code=50002)
    children = repo.list_folders(parent_id=parent["id"], owner_id="david")

    assert parent["folder_code"] == 60020
    assert child["folder_code"] == 60021
    assert child["parent_id"] == parent["id"]
    assert children[0]["name"] == "Lean Proofs"


def test_folder_http_routes_create_and_list(tmp_path):
    from fastapi.testclient import TestClient

    from hub.api import routes_folders
    from hub.api.app import create_app

    routes_folders.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    client = TestClient(create_app())

    create_response = client.post("/folders", json={"name": "API Calls", "wall": "code", "wall_code": 50006})
    list_response = client.get("/folders", params={"wall": "code"})

    assert create_response.status_code == 200
    assert create_response.json()["folder"]["folder_code"] == 60020
    assert list_response.json()["folders"][0]["name"] == "API Calls"


def test_folder_repo_supports_three_tags_search_and_tree(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = FolderRepo(db.conn)

    parent = repo.create_folder(name="Bohemian Console", owner_id="david", tags=["api", "ahk", "react"])
    child = repo.create_folder(
        name="Prediction Engines",
        parent_id=parent["id"],
        owner_id="david",
        tags=["nlp"],
        metadata={"keywords": ["markov", "prediction"]},
    )

    assert parent["tags"] == ["api", "ahk", "react"]
    assert repo.list_folders(owner_id="david", tag="api")[0]["id"] == parent["id"]
    assert repo.search_folders("markov", owner_id="david")[0]["id"] == child["id"]
    tree = repo.folder_tree(owner_id="david")
    assert tree[0]["id"] == parent["id"]
    assert tree[0]["children"][0]["id"] == child["id"]


def test_folder_repo_rejects_more_than_three_tags(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = FolderRepo(db.conn)

    try:
        repo.create_folder(name="Too Tagged", tags=["one", "two", "three", "four"])
    except ValueError as exc:
        assert "up to three tags" in str(exc)
    else:
        raise AssertionError("expected folders with more than three tags to be rejected")
