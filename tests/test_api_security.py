from starlette.datastructures import Headers

from hub.api.security import is_authorized


def test_openapi_stays_public_when_token_configured():
    assert is_authorized("/openapi.json", Headers({}), "secret-token") is True


def test_operational_endpoint_requires_token_when_configured():
    assert is_authorized("/jobs", Headers({}), "secret-token") is False


def test_operational_endpoint_accepts_bearer_token_when_configured():
    headers = Headers({"Authorization": "Bearer secret-token"})

    assert is_authorized("/jobs", headers, "secret-token") is True
