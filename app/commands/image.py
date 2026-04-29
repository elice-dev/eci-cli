from __future__ import annotations

import click

from ..utils import FilterSpec, ResourceGroup, register_list_get


@click.group("image", cls=ResourceGroup, help="List/get OS images.")
def image() -> None:
    pass


register_list_get(
    image,
    list_fn="list_images",
    get_fn="get_image",
    default_columns=("name", "size_gib", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("keywords"),
    ],
)
