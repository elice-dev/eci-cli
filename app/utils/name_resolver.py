from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import click

from ..client import ECIClient


_KIND_FOR_LIST: dict[str, str] = {
    "list_zones": "zone",
    "list_regions": "region",
    "list_instance_types": "instance type",
    "list_pricings": "pricing",
    "list_images": "image",
    "list_clusters": "cluster",
    "list_vms": "VM",
    "list_allocations": "VM allocation",
    "list_cluster_allocations": "cluster allocation",
    "list_subnets": "subnet",
    "list_vnets": "virtual network",
    "list_nics": "NIC",
    "list_public_ips": "public IP",
    "list_block_storages": "block storage",
    "list_block_snapshots": "block snapshot",
    "list_snapshot_schedulers": "snapshot scheduler",
    "list_pfs": "parallel file system",
    "list_pfs_members": "PFS member",
    "list_object_storages": "object storage",
    "list_object_users": "object storage user",
    "list_object_grants": "object storage grant",
    "list_vpns": "VPN",
}


def _kind_label(list_fn_name: str) -> str:
    return _KIND_FOR_LIST.get(list_fn_name, "item")


class NameResolver:
    FIELD_MAP: dict[str, str] = {
        "zone_id": "list_zones",
        "region_id": "list_regions",
        "instance_type_id": "list_instance_types",
        "pricing_id": "list_pricings",
        "image_id": "list_images",
        "cluster_id": "list_clusters",
        "machine_id": "list_vms",
        "attached_machine_id": "list_vms",
        "attached_subnet_id": "list_subnets",
        "attached_network_id": "list_vnets",
        "attached_network_interface_id": "list_nics",
        "block_storage_id": "list_block_storages",
        "snapshot_id": "list_block_snapshots",
        "snapshot_scheduler_id": "list_snapshot_schedulers",
        "parallel_file_system_id": "list_pfs",
        "object_storage_id": "list_object_storages",
        "object_storage_user_id": "list_object_users",
        "cluster_allocation_id": "list_cluster_allocations",
    }

    def __init__(self, client: ECIClient):
        self.client = client
        self._cache: dict[str, dict[str, str]] = {}

    def _name_of(self, item: dict) -> str:
        return item.get("name") or item.get("ip") or item.get("id", "")

    def _load(self, list_fn_name: str) -> dict[str, str]:
        if list_fn_name in self._cache:
            return self._cache[list_fn_name]

        try:
            self._cache[list_fn_name] = {
                i["id"]: self._name_of(i) for i in getattr(self.client, list_fn_name)()
            }
        except Exception as e:
            if os.environ.get("ECI_DEBUG"):
                print(
                    f"[debug] resolver._load({list_fn_name!r}) failed: {e}",
                    file=sys.stderr,
                )
            self._cache[list_fn_name] = {}

        return self._cache[list_fn_name]

    def lookup(self, field_name: str, value: Any) -> Any:
        if value in (None, ""):
            return value

        list_fn = self.FIELD_MAP.get(field_name)

        if not list_fn:
            return value

        return self._load(list_fn).get(value, value)

    def resolve(self, list_fn_name: str, name_or_id: str) -> str:
        if is_uuid(name_or_id):
            return name_or_id

        items = getattr(self.client, list_fn_name)(name_ilike=name_or_id)
        exact = [i for i in items if i.get("name") == name_or_id]

        if not exact:
            exact = [i for i in items if i.get("ip") == name_or_id]

        if not exact:
            all_items = getattr(self.client, list_fn_name)()
            exact = [i for i in all_items if i.get("ip") == name_or_id]

        kind = _kind_label(list_fn_name)

        if not exact:
            raise click.ClickException(f"no {kind} named {name_or_id!r}")

        if len(exact) > 1:
            raise click.ClickException(
                f"multiple {kind}s named {name_or_id!r}; pass UUID"
            )

        return exact[0]["id"]


def is_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except Exception:
        return False


@dataclass
class AppContext:
    client: ECIClient
    resolver: NameResolver = field(init=False)

    def __post_init__(self) -> None:
        self.resolver = NameResolver(self.client)
