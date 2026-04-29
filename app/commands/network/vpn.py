from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("vpn", cls=ResourceGroup, help="VPN gateways.")
def vpn() -> None:
    pass


register_list_get(
    vpn,
    list_fn="list_vpns",
    get_fn="get_vpn",
    default_columns=("attached_subnet", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("organization_id"),
        FilterSpec("attached_subnet_id"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@vpn.command("create")
@click.option("--subnet", "subnet_arg", required=True)
@click.pass_obj
def vpn_create(app: AppContext, subnet_arg: str) -> None:
    emit_action_result(
        app.client.create_vpn(
            attached_subnet_id=app.resolver.resolve("list_subnets", subnet_arg)
        )
    )


@vpn.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def vpn_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    if name_or_id and not name_or_id.startswith("-"):
        try:
            vpn_id = app.resolver.resolve("list_vpns", name_or_id)
        except click.ClickException:
            vpn_id = name_or_id
    else:
        vpn_id = name_or_id

    if not yes:
        click.confirm(f"Delete VPN {name_or_id}?", abort=True)
        
    emit_action_result(app.client.delete_vpn(vpn_id))
