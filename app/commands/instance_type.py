from __future__ import annotations

import click

from ..utils import FilterSpec, ResourceGroup, register_list_get


@click.group("instance-type", cls=ResourceGroup, help="List/get instance types.")
def instance_type() -> None:
    pass


register_list_get(
    instance_type,
    list_fn="list_instance_types",
    get_fn="get_instance_type",
    default_columns=("name", "cpu_vcore", "memory_gib", "activated"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("organization_id"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("activated", type="bool"),
    ],
)
