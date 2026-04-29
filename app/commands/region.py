from __future__ import annotations

import click

from ..utils import FilterSpec, ResourceGroup, register_list_get


@click.group("region", cls=ResourceGroup, help="List/get regions.")
def region() -> None:
    pass


register_list_get(
    region,
    list_fn="list_regions",
    get_fn="get_region",
    default_columns=("name",),
    filters=[FilterSpec("ids"), FilterSpec("name_ilike")],
)
