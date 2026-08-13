from fastapi.testclient import TestClient


def test_clipboard_shelf_save_list_search_copy_import(tmp_path, monkeypatch):
    db_path = tmp_path / "clipboard.sqlite3"
    monkeypatch.setenv("FIHUB_DB_PATH", str(db_path))
    monkeypatch.delenv("FIHUB_API_TOKEN", raising=False)

    from file_intelligence_hub.api import routes_clipboard
    from file_intelligence_hub.api.app import create_app

    routes_clipboard.DEFAULT_DB_PATH = db_path
    client = TestClient(create_app())

    save_response = client.post(
        "/clipboard/save",
        json={
            "body": "clipboard alpha text",
            "source_app": "AutoHotkey.exe",
            "source_window": "Test Window",
            "folder": "Clipboard",
            "tags": "alpha,test",
            "pinned": True,
        },
    )
    assert save_response.status_code == 200
    item = save_response.json()["item"]
    assert item["id"] > 0
    assert item["body"] == "clipboard alpha text"
    assert item["pinned"] is True

    list_response = client.get("/clipboard/items", params={"query": "alpha"})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert [found["id"] for found in items] == [item["id"]]

    copy_response = client.post(f"/clipboard/items/{item['id']}/copy")
    assert copy_response.status_code == 200
    assert copy_response.json()["item"]["copied_at"] is not None

    import_response = client.post(
        "/clipboard/import",
        json={"items": [{"body": "imported clip", "folder": "Imported"}]},
    )
    assert import_response.status_code == 200
    assert import_response.json()["stored"] == 1


def test_clipboard_items_route_still_accepts_existing_clients(tmp_path, monkeypatch):
    db_path = tmp_path / "clipboard.sqlite3"
    monkeypatch.setenv("FIHUB_DB_PATH", str(db_path))
    monkeypatch.delenv("FIHUB_API_TOKEN", raising=False)

    from file_intelligence_hub.api import routes_clipboard
    from file_intelligence_hub.api.app import create_app

    routes_clipboard.DEFAULT_DB_PATH = db_path
    client = TestClient(create_app())

    response = client.post("/clipboard/items", json={"body": "legacy route"})

    assert response.status_code == 200
    assert response.json()["item"]["body"] == "legacy route"
