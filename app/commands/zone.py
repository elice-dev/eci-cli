from __future__ import annotations

import click

from ..utils import FilterSpec, ResourceGroup, register_list_get


@click.group("zone", cls=ResourceGroup, help="List/get availability zones.")
def zone() -> None:
    pass


register_list_get(
    zone,
    list_fn="list_zones",
    get_fn="get_zone",
    default_columns=("name", "region"),
    filters=[FilterSpec("ids"), FilterSpec("name_ilike"), FilterSpec("region_id")],
)
