from __future__ import annotations

import json as _json

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("vnet", cls=ResourceGroup, help="Virtual networks.")
def vnet() -> None:
    pass


register_list_get(
    vnet,
    list_fn="list_vnets",
    get_fn="get_vnet",
    default_columns=("name", "network_cidr", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@vnet.command("create")
@click.option("--name", required=True)
@click.option("--cidr", "network_cidr", required=True, help="e.g. 10.0.0.0/16")
@click.pass_obj
def vnet_create(app: AppContext, name: str, network_cidr: str) -> None:
    emit_action_result(app.client.create_vnet(name=name, network_cidr=network_cidr))


@vnet.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.option("--firewall-rules", default=None, help="JSON-encoded firewall rules.")
@click.pass_obj
def vnet_update(
    app: AppContext, name_or_id: str, name: str | None, firewall_rules: str | None
) -> None:
    fields: dict = {}
    if name is not None:
        fields["name"] = name

    if firewall_rules is not None:
        fields["firewall_rules"] = _json.loads(firewall_rules)

    if not fields:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_vnet(app.resolver.resolve("list_vnets", name_or_id), **fields)
    )


@vnet.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def vnet_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    vid = app.resolver.resolve("list_vnets", name_or_id)

    if not yes:
        click.confirm(f"Delete vnet {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_vnet(vid))
