from __future__ import annotations

import click

from ..utils import AppContext, FilterSpec, ResourceGroup, register_list_get


@click.group("pricing", cls=ResourceGroup, help="List/get pricing records.")
def pricing() -> None:
    pass


def _hide_stale_vm_pricings(items: list[dict], app: AppContext) -> list[dict]:
    """Drop vm_allocation pricings whose instance_type is deactivated.

    The backend keeps historical pricing rows pointing at instance_types that
    have since been deactivated (name="removed" etc.). Surfacing them confuses
    users — they cannot launch with those pricings anyway. Filter them out
    client-side.
    """
    vm_ids_in_use = {
        p.get("resource_id")
        for p in items
        if p.get("resource_kind") == "vm_allocation" and p.get("resource_id")
    }
    if not vm_ids_in_use:
        return items
    active_vm_ids = {
        it["id"]
        for it in app.client.list_instance_types(activated=True)
        if it.get("id") in vm_ids_in_use
    }
    return [
        p
        for p in items
        if p.get("resource_kind") != "vm_allocation"
        or p.get("resource_id") in active_vm_ids
    ]


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
)
