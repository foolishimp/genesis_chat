# Implements: REQ-F-AREG-001
# Implements: REQ-F-AREG-002
# Implements: REQ-F-AREG-003
"""Config-driven adapter registry — pluggable adapters without code changes.

Adapters are declared in adapters.yml with module path, class name, and
optional config class. The registry resolves by name and instantiates
with passthrough kwargs.

Source reference: OpenClaw src/channels/plugins/load.ts registry pattern (~150 LOC).
Our adaptation is ~70 LOC Python — importlib-based, no jiti/bundler complexity.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from genesis_chat.adapter.base import MessageAdapter

try:
    import yaml
except ImportError:
    import json as _json

    class _yaml_shim:
        @staticmethod
        def safe_load(text):
            return _json.loads(text)
    yaml = _yaml_shim()


@dataclass
class AdapterEntry:
    name: str
    module: str
    cls: str
    config_class: str | None
    cli_prefix: str | None
    requires: list[str]


class AdapterRegistry:
    def __init__(self, registry_path: Path):
        data = yaml.safe_load(registry_path.read_text())
        self._entries: dict[str, AdapterEntry] = {}
        for name, entry in data.get("adapters", {}).items():
            self._entries[name] = AdapterEntry(
                name=name,
                module=entry["module"],
                cls=entry["class"],
                config_class=entry.get("config_class"),
                cli_prefix=entry.get("cli_prefix"),
                requires=entry.get("requires", []),
            )

    def resolve(self, name: str, **kwargs) -> MessageAdapter:
        """Import module, instantiate adapter class with kwargs, return adapter."""
        entry = self._entries.get(name)
        if not entry:
            available = ", ".join(sorted(self._entries.keys()))
            raise ValueError(f"Unknown adapter '{name}'. Available: {available}")

        try:
            mod = importlib.import_module(entry.module)
        except ImportError as e:
            deps = ", ".join(entry.requires) if entry.requires else "unknown"
            raise ImportError(
                f"Adapter '{name}' requires package(s): {deps}. "
                f"Install with: pip install {deps}\n"
                f"Import error: {e}"
            ) from e

        adapter_cls = getattr(mod, entry.cls)

        # If a config class is declared, instantiate it with matching kwargs
        if entry.config_class:
            config_cls = getattr(mod, entry.config_class)
            # Filter kwargs to those accepted by config class
            import inspect
            sig = inspect.signature(config_cls)
            valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            config = config_cls(**valid_kwargs)
            # Remove config kwargs, pass remaining to adapter
            remaining = {k: v for k, v in kwargs.items() if k not in sig.parameters}
            return adapter_cls(config, **remaining)
        else:
            return adapter_cls(**kwargs)

    def validate_all(self) -> dict[str, str | None]:
        """Check all adapters are importable. Returns {name: error_msg | None}."""
        results: dict[str, str | None] = {}
        for name, entry in self._entries.items():
            try:
                importlib.import_module(entry.module)
                results[name] = None
            except ImportError as e:
                deps = ", ".join(entry.requires) if entry.requires else "unknown"
                results[name] = f"Missing: {deps} ({e})"
        return results

    def available(self) -> list[str]:
        return sorted(self._entries.keys())
