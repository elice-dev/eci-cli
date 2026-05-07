from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("nic", cls=ResourceGroup, help="Network interfaces.")
def nic() -> None:
    pass


register_list_get(
    nic,
    list_fn="list_nics",
    get_fn="get_nic",
    default_columns=(
        "name",
        "ip",
        "mac",
        "attached_subnet",
        "attached_machine",
        "status",
    ),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("attached_subnet_id"),
        FilterSpec("attached_machine_id"),
        FilterSpec("dr", type="bool"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@nic.command("create", help="Create a network interface in a subnet.")
@click.option("--name", required=True)
@click.option("--subnet", "subnet_arg", required=True, help="Subnet (UUID or name).")
@click.option("--ip", default=None)
@click.option("--mac", default=None)
@click.option("--dr/--no-dr", default=False)
@click.pass_obj
def nic_create(
    app: AppContext,
    name: str,
    subnet_arg: str,
    ip: str | None,
    mac: str | None,
    dr: bool,
) -> None:
    emit_action_result(
        app.client.create_nic(
            name=name,
            attached_subnet_id=app.resolver.resolve("list_subnets", subnet_arg),
            ip=ip,
            mac=mac,
            dr=dr,
        )
    )


@nic.command("update", help="Patch NIC attributes.")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.pass_obj
def nic_update(app: AppContext, name_or_id: str, name: str | None) -> None:
    if name is None:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_nic(app.resolver.resolve("list_nics", name_or_id), name=name)
    )


@nic.command("attach", help="Attach a NIC to a VM.")
@click.argument("name_or_id")
@click.option("--vm", "vm_arg", required=True, help="VM (UUID or name).")
@click.pass_obj
def nic_attach(app: AppContext, name_or_id: str, vm_arg: str) -> None:
    emit_action_result(
        app.client.attach_nic(
            app.resolver.resolve("list_nics", name_or_id),
            app.resolver.resolve("list_vms", vm_arg),
        )
    )


@nic.command("detach", help="Detach a NIC from its VM.")
@click.argument("name_or_id")
@click.pass_obj
def nic_detach(app: AppContext, name_or_id: str) -> None:
    emit_action_result(
        app.client.attach_nic(app.resolver.resolve("list_nics", name_or_id), None)
    )


@nic.command("delete", help="Delete a NIC.")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.pass_obj
def nic_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    nid = app.resolver.resolve("list_nics", name_or_id)

    if not yes:
        click.confirm(f"Delete NIC {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_nic(nid))
