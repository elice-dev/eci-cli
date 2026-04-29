from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_ENDPOINT = "https://portal.elice.cloud/api"
CONFIG_PATH = Path(
    os.environ.get("ECI_CONFIG", str(Path.home() / ".eci" / "config.yaml"))
)


@dataclass
class Config:
    api_endpoint: str = DEFAULT_ENDPOINT
    api_token: str = ""
    zone_id: str = ""
    vm_defaults: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        data: dict = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}

        for env_key, attr in (
            ("ECI_API_ENDPOINT", "api_endpoint"),
            ("ECI_API_TOKEN", "api_token"),
            ("ECI_ZONE_ID", "zone_id"),
        ):
            if v := os.environ.get(env_key):
                data[attr] = v

        return cls(
            api_endpoint=data.get("api_endpoint") or DEFAULT_ENDPOINT,
            api_token=data.get("api_token", "") or "",
            zone_id=data.get("zone_id", "") or "",
            vm_defaults=data.get("vm_defaults") or {},
        )

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(
                {
                    "api_endpoint": self.api_endpoint,
                    "api_token": self.api_token,
                    "zone_id": self.zone_id,
                    "vm_defaults": self.vm_defaults,
                },
                f,
                sort_keys=False,
            )

        os.chmod(CONFIG_PATH, 0o600)

    def set_path(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")

        if parts[0] in {"api_endpoint", "api_token", "zone_id"} and len(parts) == 1:
            setattr(self, parts[0], value)
            return

        if parts[0] == "vm_defaults":
            node = self.vm_defaults

            for p in parts[1:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = value

            return

        raise KeyError(f"unsupported config path: {dotted}")
