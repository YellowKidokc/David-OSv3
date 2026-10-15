"""Centralized folder profile loading, validation, and matching."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path("config/folder_profiles.json")
SCHEMA_PATH = Path("schemas/folder_profiles.schema.json")
PROFILE_KEYS = {"path", "folder_role", "watch_enabled", "review_only", "protected", "parser_preferences", "routing_hints", "thresholds",
                "allowed_actions", "blocked_actions", "irrelevant_actions",
                "sidecar_writer", "report_type", "approval_floor"}

APPROVAL_FLOORS = {"preview_only", "suggest_only", "approval_required", "auto_after_threshold", "blocked"}


class FolderProfileConfigError(ValueError):
    """Raised when repo-centered folder profile config is invalid."""


@dataclass(frozen=True)
class FolderProfile:
    path: str = "*"
    folder_role: str = "general"
    watch_enabled: bool = True
    review_only: bool = True
    protected: bool = False
    parser_preferences: list[str] = field(default_factory=list)
    routing_hints: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    allowed_actions: tuple[str, ...] = ()
    blocked_actions: tuple[str, ...] = ()
    irrelevant_actions: tuple[str, ...] = ()
    sidecar_writer: str = "default"
    report_type: str = "default"
    approval_floor: str = "preview_only"

    @classmethod
    def from_dict(cls, data: dict[str, Any], defaults: "FolderProfile | None" = None) -> "FolderProfile":
        base = defaults or cls()
        return cls(
            path=str(data.get("path", base.path)),
            folder_role=str(data.get("folder_role", base.folder_role)),
            watch_enabled=bool(data.get("watch_enabled", base.watch_enabled)),
            review_only=bool(data.get("review_only", base.review_only)),
            protected=bool(data.get("protected", base.protected)),
            parser_preferences=list(data.get("parser_preferences", base.parser_preferences)),
            routing_hints=dict(data.get("routing_hints", base.routing_hints)),
            thresholds={key: float(value) for key, value in dict(data.get("thresholds", base.thresholds)).items()},
            allowed_actions=tuple(data.get("allowed_actions", base.allowed_actions)),
            blocked_actions=tuple(data.get("blocked_actions", base.blocked_actions)),
            irrelevant_actions=tuple(data.get("irrelevant_actions", base.irrelevant_actions)),
            sidecar_writer=str(data.get("sidecar_writer", base.sidecar_writer)),
            report_type=str(data.get("report_type", base.report_type)),
            approval_floor=str(data.get("approval_floor", base.approval_floor)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "folder_role": self.folder_role,
            "watch_enabled": self.watch_enabled,
            "review_only": self.review_only,
            "protected": self.protected,
            "parser_preferences": self.parser_preferences,
            "routing_hints": self.routing_hints,
            "thresholds": self.thresholds,
            "allowed_actions": list(self.allowed_actions),
            "blocked_actions": list(self.blocked_actions),
            "irrelevant_actions": list(self.irrelevant_actions),
            "sidecar_writer": self.sidecar_writer,
            "report_type": self.report_type,
            "approval_floor": self.approval_floor,
        }


class FolderProfileRegistry:
    def __init__(self, default: FolderProfile | None = None, profiles: list[FolderProfile] | None = None) -> None:
        self.default = default or FolderProfile()
        self.profiles = profiles or []

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PROFILE_PATH) -> "FolderProfileRegistry":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        validate_folder_profile_config(raw)
        default = FolderProfile.from_dict(raw.get("defaults", {}))
        profiles = [FolderProfile.from_dict(item, default) for item in raw.get("profiles", [])]
        return cls(default, profiles)

    def enabled_roots(self) -> list[Path]:
        return [Path(profile.path) for profile in self.profiles if profile.watch_enabled and profile.path != "*"]

    def match(self, file_path: str | Path) -> FolderProfile:
        candidate = os.path.normcase(str(Path(file_path).resolve()))
        best: tuple[int, FolderProfile] | None = None
        for profile in self.profiles:
            root_path = Path(profile.path).expanduser().resolve()
            root = os.path.normcase(str(root_path))
            if candidate != root and not candidate.startswith(root + os.sep):
                continue
            score = len(root_path.parts)
            if best is None or score > best[0]:
                best = (score, profile)
        return best[1] if best else self.default


def validate_folder_profile_config(raw: Any) -> None:
    """Validate the supported subset of the formal JSON schema with clear errors."""
    if not isinstance(raw, dict):
        raise FolderProfileConfigError("folder profile config must be an object")
    unknown_root = set(raw) - {"defaults", "profiles"}
    if unknown_root:
        raise FolderProfileConfigError(f"unknown root keys: {sorted(unknown_root)}")
    if "profiles" not in raw or not isinstance(raw["profiles"], list):
        raise FolderProfileConfigError("profiles must be a list")
    if "defaults" in raw:
        _validate_profile(raw["defaults"], "defaults", require_path=False)
    for index, profile in enumerate(raw["profiles"]):
        _validate_profile(profile, f"profiles[{index}]", require_path=True)


def _validate_profile(profile: Any, location: str, *, require_path: bool) -> None:
    if not isinstance(profile, dict):
        raise FolderProfileConfigError(f"{location} must be an object")
    unknown = set(profile) - PROFILE_KEYS
    if unknown:
        raise FolderProfileConfigError(f"{location} has unknown keys: {sorted(unknown)}")
    if require_path and not isinstance(profile.get("path"), str):
        raise FolderProfileConfigError(f"{location}.path must be a string")
    for key in ("path", "folder_role"):
        if key in profile and not isinstance(profile[key], str):
            raise FolderProfileConfigError(f"{location}.{key} must be a string")
    for key in ("watch_enabled", "review_only", "protected"):
        if key in profile and not isinstance(profile[key], bool):
            raise FolderProfileConfigError(f"{location}.{key} must be a boolean")
    if "parser_preferences" in profile and not _is_string_list(profile["parser_preferences"]):
        raise FolderProfileConfigError(f"{location}.parser_preferences must be a list of strings")
    if "routing_hints" in profile and not isinstance(profile["routing_hints"], dict):
        raise FolderProfileConfigError(f"{location}.routing_hints must be an object")
    if "thresholds" in profile:
        thresholds = profile["thresholds"]
        if not isinstance(thresholds, dict) or not all(isinstance(value, (int, float)) for value in thresholds.values()):
            raise FolderProfileConfigError(f"{location}.thresholds must be an object of numbers")
    for key in ("allowed_actions", "blocked_actions", "irrelevant_actions"):
        if key in profile and not _is_string_list(profile[key]):
            raise FolderProfileConfigError(f"{location}.{key} must be a list of strings")
    for key in ("sidecar_writer", "report_type"):
        if key in profile and not isinstance(profile[key], str):
            raise FolderProfileConfigError(f"{location}.{key} must be a string")
    if "approval_floor" in profile and profile["approval_floor"] not in APPROVAL_FLOORS:
        raise FolderProfileConfigError(f"{location}.approval_floor must be one of {sorted(APPROVAL_FLOORS)}")


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
