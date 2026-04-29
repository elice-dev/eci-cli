from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("ip", cls=ResourceGroup, help="Public IPs.")
def ip() -> None:
    pass


register_list_get(
    ip,
    list_fn="list_public_ips",
    get_fn="get_public_ip",
    default_columns=("ip", "attached_network_interface", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("attached_network_interface_id"),
        FilterSpec("ddos", type="bool"),
        FilterSpec("dr", type="bool"),
        FilterSpec("pricing_type"),
        FilterSpec("pricing_id"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@ip.command("create")
@click.option("--pricing", required=True)
@click.option("--dr/--no-dr", default=False)
@click.option("--ddos/--no-ddos", default=True)
@click.pass_obj
def ip_create(app: AppContext, pricing: str, dr: bool, ddos: bool) -> None:
    emit_action_result(
        app.client.create_public_ip(
            pricing_id=app.resolver.resolve("list_pricings", pricing), dr=dr, ddos=ddos
        )
    )


@ip.command("update")
@click.argument("name_or_id")
@click.option(
    "--tag", "tags", multiple=True, metavar="K=V", help="Tag k=v pairs (repeatable)."
)
@click.pass_obj
def ip_update(app: AppContext, name_or_id: str, tags: tuple[str, ...]) -> None:
    if not tags:
        raise click.ClickException("nothing to update")

    parsed: dict = {}

    for kv in tags:
        if "=" not in kv:
            raise click.ClickException(f"invalid --tag (need K=V): {kv}")
        k, v = kv.split("=", 1)
        parsed[k] = v

    emit_action_result(
        app.client.update_public_ip(
            app.resolver.resolve("list_public_ips", name_or_id), tags=parsed
        )
    )


@ip.command("attach")
@click.argument("name_or_id")
@click.option("--nic", "nic_arg", required=True)
@click.pass_obj
def ip_attach(app: AppContext, name_or_id: str, nic_arg: str) -> None:
    emit_action_result(
        app.client.attach_public_ip(
            app.resolver.resolve("list_public_ips", name_or_id),
            app.resolver.resolve("list_nics", nic_arg),
        )
    )


@ip.command("detach")
@click.argument("name_or_id")
@click.pass_obj
def ip_detach(app: AppContext, name_or_id: str) -> None:
    emit_action_result(
        app.client.attach_public_ip(
            app.resolver.resolve("list_public_ips", name_or_id), None
        )
    )


@ip.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def ip_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    pip_id = app.resolver.resolve("list_public_ips", name_or_id)

    if not yes:
        click.confirm(f"Delete public IP {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_public_ip(pip_id))
