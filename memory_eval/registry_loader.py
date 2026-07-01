from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from .models import Case, LoadedRegistry
from .registry_default import REGISTRY as DEFAULT_REGISTRY
from runtime_paths import RuntimePaths


def _agent_home() -> Path:
    return RuntimePaths.from_agent_home().agent_home


def _case_from_mapping(payload: dict) -> Case:
    return Case(
        id=str(payload["id"]),
        category=str(payload["category"]),
        query=str(payload["query"]),
        expected_fields=list(payload.get("expected_fields", [])),
        expected_layer=str(payload["expected_layer"]),
        expected_min_score=float(payload.get("expected_min_score", 0.0)),
        conflict_expected=bool(payload.get("conflict_expected", False)),
        temporal_context=payload.get("temporal_context"),
        synthetic_hits=tuple(payload.get("synthetic_hits", ())),
    )


def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load registry module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_registry(name: str, payload: object, source_path: Path | None = None) -> LoadedRegistry:
    if not isinstance(payload, list):
        return LoadedRegistry(name=name, cases=[], error="registry must be a list", source_path=source_path)
    try:
        cases = [_case_from_mapping(item) for item in payload]
    except Exception as exc:  # pragma: no cover - scoped error reporting
        return LoadedRegistry(name=name, cases=[], error=str(exc), source_path=source_path)
    return LoadedRegistry(name=name, cases=cases, source_path=source_path)


def _default_registry() -> LoadedRegistry:
    return _normalize_registry("default", DEFAULT_REGISTRY)


def _production_registry(required: bool = False) -> LoadedRegistry:
    private = RuntimePaths.from_agent_home(_agent_home()).production_registry
    if not private.exists():
        if required:
            raise FileNotFoundError(f"production registry not found: {private}")
        return LoadedRegistry(name="production", cases=[], error=None, source_path=private)
    try:
        module = _load_module_from_path(private)
        payload = getattr(module, "REGISTRY", None)
    except Exception as exc:
        return LoadedRegistry(name="production", cases=[], error=str(exc), source_path=private)
    return _normalize_registry("production", payload, private)


def load_registries(registry_name: str = "default") -> list[LoadedRegistry]:
    if registry_name == "default":
        return [_default_registry()]
    if registry_name == "production":
        return [_production_registry(required=True)]
    if registry_name == "all":
        loaded = [_default_registry()]
        production = _production_registry()
        if production.source_path and production.source_path.exists():
            loaded.append(production)
        return loaded
    raise ValueError(f"unknown registry selector: {registry_name}")
