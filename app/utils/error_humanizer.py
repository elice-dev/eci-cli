"""Humanize API errors — replace opaque UUIDs with names, add hints.

The API returns stable identifiers (UUIDs) in error payloads, which is correct
for a stable wire protocol but unfriendly for end users / AI agents who only
know the resource by name (e.g. `--instance-type C-2`).

This module is the *one-way* humanizing layer that runs on the output side:
input still goes name → UUID via `NameResolver.resolve`; errors come back
UUID → name via `humanize_eci_error`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..client import ECIClient, ECIError
from ..config import Config
from .name_resolver import NameResolver


_RESOURCE_KIND_TO_LIST_FN: dict[str, str] = {
    "instance_type": "list_instance_types",
    "image": "list_images",
    "zone": "list_zones",
    "region": "list_regions",
    "pricing": "list_pricings",
    "block_storage": "list_block_storages",
    "block_storage_image": "list_images",
    "virtual_machine": "list_vms",
    "machine": "list_vms",
    "network_interface": "list_nics",
    "subnet": "list_subnets",
    "virtual_network": "list_vnets",
    "public_ip": "list_public_ips",
    "cluster": "list_clusters",
    "object_storage": "list_object_storages",
    "parallel_file_system": "list_pfs",
}


@dataclass
class HumanizedError:
    title: str
    lines: list[str]
    hint: str | None = None


def _split_resource(s: str) -> tuple[str, str | None] | None:
    """'instance_type.a7fab967-...' -> ('instance_type', 'a7fab967-...')
       'public_ip'                  -> ('public_ip', None)

    Org-wide quotas (public_ip, vcpu, virtual_network, ...) come without
    a UUID since they cap a kind rather than a specific resource.
    """
    if not isinstance(s, str) or not s:
        return None
    if "." in s:
        kind, _, uuid = s.partition(".")
        return kind, (uuid or None)
    return s, None


_QUOTA_KIND_HINTS: dict[str, str] = {
    "public_ip": (
        "Free a public IP:  eci network ip delete <UUID>\n"
        "      Or skip on launch: re-run with --no-public-ip"
    ),
    "virtual_network": "Delete an unused vnet: eci network vnet delete <UUID>",
    "block_storage": "Delete unused block storage: eci storage block delete <UUID>",
}


def _lookup_name(resolver: NameResolver, kind: str, uuid: str) -> str | None:
    list_fn = _RESOURCE_KIND_TO_LIST_FN.get(kind)
    if not list_fn:
        return None
    try:
        items = getattr(resolver.client, list_fn)()
    except Exception:
        return None
    for item in items:
        if item.get("id") == uuid:
            return item.get("name") or item.get("ip")
    return None


def _quota_alternatives(
    resolver: NameResolver, full_kind: str, full_uuid: str
) -> list[str]:
    """For a fully-used resource quota, suggest other items of the same kind
    that still have headroom. Best-effort: requires both the org-usage API
    and a listing of the same kind to be available."""
    list_fn = _RESOURCE_KIND_TO_LIST_FN.get(full_kind)
    if not list_fn:
        return []
    try:
        usage = resolver.client.organization_resource_usage() or {}
    except Exception:
        return []

    used_by_id: dict[str, int] = {}
    for tier in ("ondemand", "spot", "reserved"):
        tier_data = usage.get(tier) or {}
        if not isinstance(tier_data, dict):
            continue
        compute = tier_data.get("compute") or {}
        types = compute.get("instance_types") or {}
        if isinstance(types, dict):
            for k, v in types.items():
                used_by_id[k] = used_by_id.get(k, 0) + int(v or 0)

    try:
        items = getattr(resolver.client, list_fn)()
    except Exception:
        return []

    out: list[str] = []
    for item in items:
        item_id = item.get("id")
        if item_id == full_uuid:
            continue
        name = item.get("name")
        if not name:
            continue
        used = used_by_id.get(item_id, 0)
        out.append(f"{name} (used {used})")
        if len(out) >= 3:
            break
    return out


def humanize_eci_error(err: ECIError) -> HumanizedError | None:
    """Return a structured human-friendly view of an ECIError, or None if
    we cannot enrich it. Caller falls back to raw `str(err)` on None."""
    if err.status != 409 or err.code != "resource_quota_exceed":
        return _humanize_generic(err)

    detail = err.detail if isinstance(err.detail, dict) else {}
    resource_str = detail.get("resource")
    used = detail.get("used")
    limit = detail.get("limit")

    parsed = _split_resource(resource_str) if isinstance(resource_str, str) else None
    if not parsed:
        return None

    kind, uuid = parsed
    name = _try_lookup_name(kind, uuid) if uuid else None
    if name:
        label = f"{kind} '{name}'"
    elif uuid:
        label = f"{kind} {uuid}"
    else:
        label = kind

    lines = [f"Resource: {label}"]
    if name and uuid:
        lines.append(f"          ({uuid})")
    if used is not None and limit is not None:
        lines.append(f"Quota:    used {used} / limit {limit}")

    hint: str | None = None
    if uuid:
        alts = _try_alternatives(kind, uuid)
        if alts:
            hint = (
                "Try a different "
                + kind
                + " with available quota:\n  "
                + "\n  ".join(alts)
            )
    if hint is None:
        hint = _QUOTA_KIND_HINTS.get(kind)

    return HumanizedError(title="Resource quota exceeded", lines=lines, hint=hint)


def _humanize_generic(err: ECIError) -> HumanizedError | None:
    """For non-quota errors, try to swap UUIDs in `detail.resource` for names."""
    if not isinstance(err.detail, dict):
        return None
    resource_str = err.detail.get("resource")
    parsed = _split_resource(resource_str) if isinstance(resource_str, str) else None
    if not parsed:
        return None

    kind, uuid = parsed
    if not uuid:
        return None
    name = _try_lookup_name(kind, uuid)
    if not name:
        return None

    return HumanizedError(
        title=f"[{err.status}{' ' + err.code if err.code else ''}] {err.message}",
        lines=[f"Resource: {kind} '{name}' ({uuid})"],
    )


def _try_lookup_name(kind: str, uuid: str) -> str | None:
    """Look up a name via a fresh client. Best-effort — returns None on any failure."""
    try:
        cfg = Config.load()
        if not cfg.api_token:
            return None
        resolver = NameResolver(ECIClient(cfg))
        return _lookup_name(resolver, kind, uuid)
    except Exception:
        return None


def _try_alternatives(kind: str, uuid: str) -> list[str]:
    try:
        cfg = Config.load()
        if not cfg.api_token:
            return []
        resolver = NameResolver(ECIClient(cfg))
        return _quota_alternatives(resolver, kind, uuid)
    except Exception:
        return []


def format_humanized(h: HumanizedError) -> str:
    parts: list[str] = [h.title]
    parts.extend(f"  {line}" for line in h.lines)
    if h.hint:
        parts.append("")
        parts.append("Hint: " + h.hint)
    return "\n".join(parts)


def render_eci_error_to_stderr(err: ECIError, err_console: Any) -> None:
    """Render an ECIError to stderr, humanizing if possible."""
    h = None
    try:
        h = humanize_eci_error(err)
    except Exception:
        h = None
    if h is None:
        err_console.print(f"[red]API error[/red]: {err}")
        return
    err_console.print(f"[red]{h.title}[/red]")
    for line in h.lines:
        err_console.print(f"  {line}")
    if h.hint:
        err_console.print("")
        err_console.print(f"[yellow]Hint:[/yellow] {h.hint}")
