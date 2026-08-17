"""Config-backed API action registry for React and bridge clients.

The registry is intentionally file-backed and secret-free: it lets the UI and
AutoHotkey/Rust bridges discover the same small set of saved Hub actions without
hard-coding menus in multiple places.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_ACTIONS_PATH = Path("config/top_of_mind/api_actions.example.json")
REQUIRED_ACTION_KEYS = {"id", "label", "method", "endpoint"}
ALLOWED_METHODS = {"GET", "POST", "PATCH", "DELETE"}


class ApiActionRegistryError(ValueError):
    """Raised when an API action registry file is invalid."""


def load_api_action_registry(path: str | Path = DEFAULT_ACTIONS_PATH) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {"version": 1, "groups": [], "actions": []}
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    validate_api_action_registry(raw)
    return raw


def validate_api_action_registry(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise ApiActionRegistryError("api action registry must be an object")
    if not isinstance(raw.get("actions"), list):
        raise ApiActionRegistryError("api action registry requires an actions list")
    if "groups" in raw and not isinstance(raw["groups"], list):
        raise ApiActionRegistryError("api action registry groups must be a list")
    seen: set[str] = set()
    for index, action in enumerate(raw["actions"]):
        _validate_action(action, index, seen)


def _validate_action(action: Any, index: int, seen: set[str]) -> None:
    if not isinstance(action, dict):
        raise ApiActionRegistryError(f"actions[{index}] must be an object")
    missing = REQUIRED_ACTION_KEYS - set(action)
    if missing:
        raise ApiActionRegistryError(f"actions[{index}] missing keys: {sorted(missing)}")
    action_id = str(action["id"])
    if action_id in seen:
        raise ApiActionRegistryError(f"duplicate action id: {action_id}")
    seen.add(action_id)
    method = str(action["method"]).upper()
    if method not in ALLOWED_METHODS:
        raise ApiActionRegistryError(f"actions[{index}].method is not supported: {method}")
    endpoint = str(action["endpoint"])
    if not endpoint.startswith("/") or ".." in endpoint:
        raise ApiActionRegistryError(f"actions[{index}].endpoint must be a safe absolute API path")
    for object_key in ("default_payload", "input_schema", "result_card", "ahk_binding", "metadata"):
        if object_key in action and not isinstance(action[object_key], dict):
            raise ApiActionRegistryError(f"actions[{index}].{object_key} must be an object")


def list_api_actions(path: str | Path = DEFAULT_ACTIONS_PATH, *, group: str | None = None) -> dict[str, Any]:
    registry = load_api_action_registry(path)
    actions = registry.get("actions", [])
    if group:
        actions = [action for action in actions if action.get("group") == group]
    return {**registry, "actions": actions}


def get_api_action(action_id: str, path: str | Path = DEFAULT_ACTIONS_PATH) -> dict[str, Any]:
    for action in load_api_action_registry(path).get("actions", []):
        if action.get("id") == action_id:
            return action
    raise KeyError(f"api action not found: {action_id}")
