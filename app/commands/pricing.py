from __future__ import annotations

import click

from ..utils import AppContext, FilterSpec, ResourceGroup, register_list_get


@click.group("pricing", cls=ResourceGroup, help="List/get pricing records.")
def pricing() -> None:
    pass


def _hide_stale_vm_pricings(items: list[dict], app: AppContext) -> list[dict]:
    """Drop stale vm_allocation pricings and sort with vm_allocation first.

    The backend keeps historical pricing rows pointing at instance_types that
    have since been deactivated (name="removed" etc.). Surfacing them confuses
    users — they cannot launch with those pricings anyway. Filter them out
    client-side, then sort so vm_allocation is on top (most common case) with
    a stable secondary sort by pricing_type and name.
    """
    vm_ids_in_use = {
        p.get("resource_id")
        for p in items
        if p.get("resource_kind") == "vm_allocation" and p.get("resource_id")
    }
    if vm_ids_in_use:
        active_vm_ids = {
            it["id"]
            for it in app.client.list_instance_types(activated=True)
            if it.get("id") in vm_ids_in_use
        }
        items = [
            p
            for p in items
            if p.get("resource_kind") != "vm_allocation"
            or p.get("resource_id") in active_vm_ids
        ]

    def _sort_key(p: dict) -> tuple[int, str, str, str]:
        kind = p.get("resource_kind") or ""
        return (
            0 if kind == "vm_allocation" else 1,
            kind,
            p.get("pricing_type") or "",
            p.get("name") or "",
        )

    return sorted(items, key=_sort_key)


register_list_get(
    pricing,
    list_fn="list_pricings",
    get_fn="get_pricing",
    default_columns=(
        "name",
        "resource_kind",
        "pricing_type",
        "price_per_hour",
        "activated",
    ),
    filters=[
        FilterSpec("ids"),
        FilterSpec("organization_id"),
        FilterSpec("zone_id"),
        FilterSpec("resource_kind"),
        FilterSpec("resource_ids", resolver="list_instance_types"),
        FilterSpec("pricing_type"),
        FilterSpec("activated", type="bool"),
        FilterSpec("name_ilike"),
    ],
    transform=_hide_stale_vm_pricings,
    column_labels={"price_per_hour": "price_per_hour (KRW)"},
)
