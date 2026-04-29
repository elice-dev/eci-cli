from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("vm", cls=ResourceGroup, help="Virtual machines.")
def vm() -> None:
    pass


register_list_get(
    vm,
    list_fn="list_vms",
    get_fn="get_vm",
    default_columns=("name", "status", "instance_type", "always_on"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("status"),
        FilterSpec("dr", type="bool"),
        FilterSpec("cluster_id"),
        FilterSpec("instance_type_id"),
        FilterSpec("pricing_type"),
        FilterSpec("pricing_id"),
        FilterSpec("tags"),
    ],
)


@vm.command("create", help="Create a VM (without disk/NIC/IP — see `launch`).")
@click.option("--name", required=True)
@click.option(
    "--pricing",
    required=True,
    help="VM pricing name (e.g. 'M-8'). Determines the instance type.",
)
@click.option("--username", required=True)
@click.option(
    "--password", required=True, prompt=True, hide_input=True, confirmation_prompt=False
)
@click.option("--always-on/--no-always-on", default=False)
@click.option("--dr/--no-dr", default=False)
@click.option("--on-init-script", default="")
@click.pass_obj
def vm_create(
    app: AppContext,
    name: str,
    pricing: str,
    username: str,
    password: str,
    always_on: bool,
    dr: bool,
    on_init_script: str,
) -> None:
    pricing_id = app.resolver.resolve("list_pricings", pricing)
    pricing_obj = app.client.get_pricing(pricing_id)

    if pricing_obj.get("resource_kind") != "vm_allocation" or not pricing_obj.get(
        "resource_id"
    ):
        raise click.ClickException(
            f"pricing {pricing!r} is not a VM pricing "
            f"(resource_kind={pricing_obj.get('resource_kind')!r})"
        )

    emit_action_result(
        app.client.create_vm(
            name=name,
            instance_type_id=pricing_obj["resource_id"],
            pricing_id=pricing_id,
            username=username,
            password=password,
            always_on=always_on,
            dr=dr,
            on_init_script=on_init_script,
        )
    )


@vm.command("update", help="Patch VM attributes.")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.option("--instance-type", "instance_type", default=None)
@click.option("--pricing", default=None)
@click.option("--always-on/--no-always-on", default=None)
@click.pass_obj
def vm_update(
    app: AppContext,
    name_or_id: str,
    name: str | None,
    instance_type: str | None,
    pricing: str | None,
    always_on: bool | None,
) -> None:
    fields: dict = {}

    if name is not None:
        fields["name"] = name

    if instance_type is not None:
        fields["instance_type_id"] = app.resolver.resolve(
            "list_instance_types", instance_type
        )

    if pricing is not None:
        fields["pricing_id"] = app.resolver.resolve("list_pricings", pricing)

    if always_on is not None:
        fields["always_on"] = always_on

    if not fields:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_vm(app.resolver.resolve("list_vms", name_or_id), **fields)
    )


@vm.command(
    "delete", help="Delete a VM (cascade-deletes attached disks/NICs/IPs by default)."
)
@click.argument("name_or_id")
@click.option("--cascade/--no-cascade", default=True, show_default=True)
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.pass_obj
def vm_delete(app: AppContext, name_or_id: str, cascade: bool, yes: bool) -> None:

    vm_id = app.resolver.resolve("list_vms", name_or_id)
    if not yes:
        click.confirm(f"Delete VM {name_or_id} (cascade={cascade})?", abort=True)

    if cascade:
        ips = app.client.list_public_ips(attached_network_interface_id="notnull")
        nics = app.client.list_nics(attached_machine_id=vm_id)
        nic_ids = {n["id"] for n in nics}

        for ip in ips:
            if ip.get("attached_network_interface_id") in nic_ids:
                app.client.attach_public_ip(ip["id"], None)
                app.client.delete_public_ip(ip["id"])

        for nic in nics:
            app.client.attach_nic(nic["id"], None)
            app.client.delete_nic(nic["id"])

        for bs in app.client.list_block_storages(attached_machine_id=vm_id):
            app.client.attach_block_storage(bs["id"], None)
            app.client.delete_block_storage(bs["id"])

    emit_action_result(app.client.delete_vm(vm_id))


@vm.command("start", help="Boot a VM (create allocation).")
@click.argument("name_or_id")
@click.pass_obj
def vm_start(app: AppContext, name_or_id: str) -> None:
    emit_action_result(
        app.client.create_allocation(app.resolver.resolve("list_vms", name_or_id))
    )


@vm.command("stop", help="Stop a VM (delete current allocation).")
@click.argument("name_or_id")
@click.pass_obj
def vm_stop(app: AppContext, name_or_id: str) -> None:
    allocs = app.client.list_allocations(
        machine_id=app.resolver.resolve("list_vms", name_or_id)
    )

    if not allocs:
        raise click.ClickException(f"VM {name_or_id} has no active allocation")

    for a in allocs:
        if not a.get("terminated"):
            emit_action_result(app.client.delete_allocation(a["id"]))
            return

    raise click.ClickException("all allocations already terminated")
