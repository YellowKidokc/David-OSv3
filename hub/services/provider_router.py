"""Provider router — send() to any OpenAI-compatible endpoint.

Purpose: Replace hardcoded DeepSeek forwarding with a pluggable provider registry.
One send() function, N brains. Reads config/providers.json at startup.

Date: 2026-07-14
codex: services/provider_router.py — provider registry + send() router
Status: UNTESTED (wire-up in routes_openai_compat.py pending)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Config path relative to repo root (same dir as folder_profiles.py)
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
PROVIDERS_PATH = CONFIG_DIR / "providers.json"


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    base_url: str
    model: str
    key_env: str
    key: str
    priority: int
    enabled: bool
    auto_approved: bool
    tags: list[str]
    notes: str

    @property
    def resolved_key(self) -> str:
        if self.key_env:
            return os.environ.get(self.key_env, "").strip()
        return self.key.strip()

    @property
    def has_key(self) -> bool:
        return bool(self.resolved_key)

    def masked_dict(self) -> dict[str, Any]:
        """Return provider data with key hidden (for API responses)."""
        return {
            "id": self.id,
            "label": self.label,
            "base_url": self.base_url,
            "model": self.model,
            "key_env": self.key_env,
            "key": "***" if self.resolved_key else "",
            "priority": self.priority,
            "enabled": self.enabled,
            "auto_approved": self.auto_approved,
            "tags": self.tags,
            "notes": self.notes,
        }


def _load_raw() -> dict[str, Any]:
    if not PROVIDERS_PATH.exists():
        return {"providers": [], "default_provider": None, "fallback_order": []}
    return json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))


def _save_raw(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROVIDERS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _to_provider(raw: dict[str, Any]) -> Provider:
    return Provider(
        id=raw["id"],
        label=raw.get("label", raw["id"]),
        base_url=raw.get("base_url", "").rstrip("/"),
        model=raw.get("model", "auto"),
        key_env=raw.get("key_env", ""),
        key=raw.get("key", ""),
        priority=raw.get("priority", 100),
        enabled=raw.get("enabled", True),
        auto_approved=raw.get("auto_approved", False),
        tags=raw.get("tags", []),
        notes=raw.get("notes", ""),
    )


def _from_provider(p: Provider) -> dict[str, Any]:
    return {
        "id": p.id,
        "label": p.label,
        "base_url": p.base_url,
        "model": p.model,
        "key_env": p.key_env,
        "key": p.key,
        "priority": p.priority,
        "enabled": p.enabled,
        "auto_approved": p.auto_approved,
        "tags": p.tags,
        "notes": p.notes,
    }


class ProviderRegistry:
    """In-memory registry loaded from providers.json."""

    def __init__(self) -> None:
        self._data = _load_raw()
        self._providers: dict[str, Provider] = {}
        self._reload()

    def _reload(self) -> None:
        self._providers = {
            raw["id"]: _to_provider(raw)
            for raw in self._data.get("providers", [])
        }

    def _save(self) -> None:
        self._data["providers"] = [_from_provider(p) for p in self._providers.values()]
        _save_raw(self._data)
        self._reload()

    # ── CRUD ───────────────────────────────────────────────────────────

    def list(self) -> list[Provider]:
        return sorted(self._providers.values(), key=lambda p: p.priority)

    def get(self, provider_id: str) -> Provider | None:
        return self._providers.get(provider_id)

    def create(self, raw: dict[str, Any]) -> Provider:
        provider_id = raw["id"]
        if provider_id in self._providers:
            raise ValueError(f"Provider '{provider_id}' already exists")
        p = _to_provider(raw)
        self._providers[provider_id] = p
        self._save()
        return p

    def update(self, provider_id: str, raw: dict[str, Any]) -> Provider:
        if provider_id not in self._providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        merged = _from_provider(self._providers[provider_id])
        merged.update(raw)
        p = _to_provider(merged)
        self._providers[provider_id] = p
        self._save()
        return p

    def delete(self, provider_id: str) -> None:
        if provider_id not in self._providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        del self._providers[provider_id]
        self._save()

    # ── Routing ────────────────────────────────────────────────────────

    def default_provider(self) -> Provider | None:
        default_id = self._data.get("default_provider")
        if default_id:
            p = self._providers.get(default_id)
            if p and p.enabled:
                return p
        # Fall back to highest-priority enabled provider
        for p in self.list():
            if p.enabled:
                return p
        return None

    def resolve(self, provider_id: str | None = None) -> Provider | None:
        if provider_id:
            p = self._providers.get(provider_id)
            if p and p.enabled:
                return p
        return self.default_provider()

    def fallback_chain(self) -> list[Provider]:
        """Return enabled providers in priority order."""
        return [p for p in self.list() if p.enabled]


# ── Global singleton ─────────────────────────────────────────────────

_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reload_registry() -> ProviderRegistry:
    global _registry
    _registry = ProviderRegistry()
    return _registry


# ── send() — the one function ────────────────────────────────────────

def _build_payload(
    messages: list[dict[str, Any]],
    model: str,
    temperature: float | None,
    max_tokens: int | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": m["role"], "content": m.get("content", "")}
            for m in messages
            if isinstance(m.get("content"), str) and m.get("content", "").strip()
        ],
        "stream": False,
    }
    if not payload["messages"]:
        payload["messages"] = [{"role": "user", "content": ""}]
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _call_provider(
    provider: Provider,
    payload: dict[str, Any],
    timeout: float = 60.0,
) -> tuple[str, dict[str, Any]]:
    key = provider.resolved_key
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{provider.base_url}/chat/completions",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    except TimeoutError as exc:
        raise RuntimeError("request timed out") from exc

    try:
        content = str(response_body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("unexpected response shape from provider") from exc

    metadata = {
        "provider": provider.id,
        "provider_label": provider.label,
        "model": payload.get("model", provider.model),
        "base_url": provider.base_url,
    }
    return content, metadata


def send(
    messages: list[dict[str, Any]],
    *,
    provider_id: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float = 60.0,
    fallback: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Send messages to a provider. Returns (content, metadata).

    If provider_id is given, try that provider first.
    If fallback is True and the first provider fails, try the fallback chain.
    If no provider works, raises RuntimeError.
    """
    registry = get_registry()
    providers_to_try: list[Provider] = []

    if provider_id:
        p = registry.resolve(provider_id)
        if p:
            providers_to_try.append(p)

    if fallback:
        for p in registry.fallback_chain():
            if p not in providers_to_try:
                providers_to_try.append(p)

    if not providers_to_try:
        raise RuntimeError("No enabled providers configured")

    last_error = ""
    for provider in providers_to_try:
        if provider.model == "auto" and not model:
            raise RuntimeError(f"Provider '{provider.id}' uses model='auto' but no model specified")
        use_model = model or provider.model
        payload = _build_payload(messages, use_model, temperature, max_tokens)
        try:
            content, metadata = _call_provider(provider, payload, timeout=timeout)
            return content, metadata
        except RuntimeError as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(f"All providers failed. Last error: {last_error}")


def send_with_ledger(
    messages: list[dict[str, Any]],
    *,
    provider_id: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float = 60.0,
    fallback: bool = True,
    source: str = "router",
) -> tuple[str, dict[str, Any]]:
    """Same as send() but logs to the ledger before returning."""
    content, metadata = send(
        messages,
        provider_id=provider_id,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        fallback=fallback,
    )
    # Ledger entry (minimal — full ledger integration in Step 3)
    ledger_line = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "provider": metadata.get("provider"),
        "model": metadata.get("model"),
        "prompt_tokens": sum(len(m.get("content", "").split()) for m in messages) // 2,
        "ok": True,
    }
    # TODO: write to ledger_entries table in Step 3
    return content, metadata
