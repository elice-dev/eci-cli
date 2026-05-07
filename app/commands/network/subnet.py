from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("subnet", cls=ResourceGroup, help="Subnets.")
def subnet() -> None:
    pass


register_list_get(
    subnet,
    list_fn="list_subnets",
    get_fn="get_subnet",
    default_columns=("name", "attached_network", "network_gw", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("attached_network_id"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@subnet.command("create", help="Create a subnet inside a vnet.")
@click.option("--name", required=True)
@click.option("--network", "network_arg", required=True, help="vnet (UUID or name).")
@click.option("--gateway", "network_gw", required=True)
@click.option("--purpose", default="virtual_machine", show_default=True)
@click.pass_obj
def subnet_create(
    app: AppContext, name: str, network_arg: str, network_gw: str, purpose: str
) -> None:
    emit_action_result(
        app.client.create_subnet(
            name=name,
            attached_network_id=app.resolver.resolve("list_vnets", network_arg),
            network_gw=network_gw,
            purpose=purpose,
        )
    )


@subnet.command("update", help="Patch subnet attributes.")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.pass_obj
def subnet_update(app: AppContext, name_or_id: str, name: str | None) -> None:
    if name is None:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_subnet(
            app.resolver.resolve("list_subnets", name_or_id), name=name
        )
    )


@subnet.command("delete", help="Delete a subnet.")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.pass_obj
def subnet_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    sid = app.resolver.resolve("list_subnets", name_or_id)

    if not yes:
        click.confirm(f"Delete subnet {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_subnet(sid))
