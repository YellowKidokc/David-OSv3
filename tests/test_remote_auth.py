from fastapi.testclient import TestClient

from hub.api.app import create_app


def test_api_routes_work_without_remote_token(monkeypatch):
    monkeypatch.delenv("FIHUB_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/jobs/stats")

    assert response.status_code == 200


def test_remote_token_protects_operational_routes(monkeypatch):
    monkeypatch.setenv("FIHUB_API_TOKEN", "test-token")
    client = TestClient(create_app())

    missing = client.get("/jobs/stats")
    wrong = client.get("/jobs/stats", headers={"x-fihub-token": "wrong"})
    header = client.get("/jobs/stats", headers={"x-fihub-token": "test-token"})
    bearer = client.get("/jobs/stats", headers={"authorization": "Bearer test-token"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert header.status_code == 200
    assert bearer.status_code == 200


def test_remote_token_leaves_openapi_readable(monkeypatch):
    monkeypatch.setenv("FIHUB_API_TOKEN", "test-token")
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
