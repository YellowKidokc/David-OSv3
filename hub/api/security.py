"""Token authentication helpers for local/LAN API access."""
from __future__ import annotations

import os
from secrets import compare_digest

from fastapi import Request
from starlette.datastructures import Headers
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

PUBLIC_PATHS = {"/docs", "/redoc", "/openapi.json"}


def is_authorized(path: str, headers: Headers, token: str | None) -> bool:
    """Return whether a request path/headers pair satisfies token policy."""
    if not token or path in PUBLIC_PATHS:
        return True
    supplied = headers.get("x-api-token") or headers.get("x-fihub-token")
    authorization = headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    return bool(supplied and compare_digest(supplied, token))


class ApiTokenMiddleware(BaseHTTPMiddleware):
    """Require a shared bearer token when FIHUB_API_TOKEN is configured.

    Local development can run without a token by leaving FIHUB_API_TOKEN unset.
    LAN/server mode should always set FIHUB_API_TOKEN and pass it as either
    `Authorization: Bearer <token>` or `X-API-Token: <token>`.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if os.environ.get('FIHUB_SEARCH_ONLY') == '1' and request.url.path not in {'/search/health', '/search/exact', '/search/locations'}:
            return JSONResponse(status_code=403, content={'detail': 'This launcher enables file search only'})
        token = os.environ.get("FIHUB_API_TOKEN")
        if not is_authorized(request.url.path, request.headers, token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
