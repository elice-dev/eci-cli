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
        # Create parent dir with 0o700 from the start so the directory entry
        # never appears world/group-readable. mkdir(mode=...) honors the
        # umask, so chmod the result to be sure.
        parent = CONFIG_PATH.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(parent, 0o700)
        except OSError:
            pass

        # Write to a sibling temp file at 0o600, then atomically rename.
        # Avoids the TOCTOU window where the real config file existed at
        # default umask perms (0o644) between open() and chmod().
        payload = yaml.safe_dump(
            {
                "api_endpoint": self.api_endpoint,
                "api_token": self.api_token,
                "zone_id": self.zone_id,
                "vm_defaults": self.vm_defaults,
            },
            sort_keys=False,
        )
        tmp_path = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".tmp")
        fd = os.open(
            str(tmp_path),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(payload)
            os.replace(str(tmp_path), str(CONFIG_PATH))
        except BaseException:
            try:
                os.unlink(str(tmp_path))
            except OSError:
                pass
            raise

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

        raise KeyError(
            f"unsupported config path: {dotted}. "
            f"Valid: api_endpoint, api_token, zone_id, vm_defaults.<spec>.<field>"
        )
