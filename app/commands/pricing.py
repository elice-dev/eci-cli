from __future__ import annotations

import click

from ..utils import FilterSpec, ResourceGroup, register_list_get


@click.group("pricing", cls=ResourceGroup, help="List/get pricing records.")
def pricing() -> None:
    pass


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
)
