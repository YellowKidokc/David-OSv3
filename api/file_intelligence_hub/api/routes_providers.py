"""Provider registry API — CRUD over config/providers.json.

Purpose: HTTP surface for the "+" button. List, add, edit, delete providers.
Keys are masked in responses. The actual send() logic lives in
services/provider_router.py.

Date: 2026-07-14
codex: api/routes_providers.py — provider registry REST API
Status: UNTESTED
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from file_intelligence_hub.services.provider_router import get_registry, Provider

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderCreate(BaseModel):
    id: str
    label: str
    base_url: str
    model: str = "auto"
    key_env: str = ""
    key: str = ""
    priority: int = 100
    enabled: bool = True
    auto_approved: bool = False
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


class ProviderUpdate(BaseModel):
    label: str | None = None
    base_url: str | None = None
    model: str | None = None
    key_env: str | None = None
    key: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    auto_approved: bool | None = None
    tags: list[str] | None = None
    notes: str | None = None


@router.get("")
def list_providers() -> dict:
    registry = get_registry()
    return {
        "providers": [p.masked_dict() for p in registry.list()],
        "default_provider": registry._data.get("default_provider"),
        "fallback_order": [p.id for p in registry.fallback_chain()],
    }


@router.get("/{provider_id}")
def get_provider(provider_id: str) -> dict:
    registry = get_registry()
    p = registry.get(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    return {"provider": p.masked_dict()}


@router.post("")
def create_provider(request: ProviderCreate) -> dict:
    registry = get_registry()
    try:
        p = registry.create(request.model_dump())
        return {"provider": p.masked_dict(), "created": True}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{provider_id}")
def update_provider(provider_id: str, request: ProviderUpdate) -> dict:
    registry = get_registry()
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        p = registry.update(provider_id, updates)
        return {"provider": p.masked_dict(), "updated": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{provider_id}")
def delete_provider(provider_id: str) -> dict:
    registry = get_registry()
    try:
        registry.delete(provider_id)
        return {"deleted": True, "id": provider_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{provider_id}/test")
def test_provider(provider_id: str) -> dict:
    """Quick health check: send a minimal request to the provider."""
    from file_intelligence_hub.services.provider_router import send
    registry = get_registry()
    p = registry.get(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    try:
        content, metadata = send(
            [{"role": "user", "content": "Say 'ok' and nothing else."}],
            provider_id=provider_id,
            max_tokens=10,
            fallback=False,
        )
        return {"ok": True, "response": content, "metadata": metadata}
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
