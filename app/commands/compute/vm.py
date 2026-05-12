from __future__ import annotations

import sys

import click

from ...client import VMStatus, is_active_allocation
from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    console,
    emit_action_result,
    register_list_get,
    render_list,
    render_one,
)
from ._pricing import PriceType, resolve_create_pricing


def _is_tty() -> bool:
    return sys.stdin.isatty()


@click.group("vm", cls=ResourceGroup, help="Virtual machines.")
def vm() -> None:
    pass


def _attach_public_ips(vms: list[dict], app: AppContext) -> list[dict]:
    if not vms:
        return vms
    vm_ids = {v["id"] for v in vms}
    nic_to_vm: dict[str, str] = {}
    for n in app.client.list_nics():
        attached = n.get("attached_machine_id")
        if isinstance(attached, str) and attached in vm_ids:
            nic_to_vm[n["id"]] = attached
    ips_by_vm: dict[str, list[str]] = {}
    for ip in app.client.list_public_ips():
        nic_id = ip.get("attached_network_interface_id")
        if nic_id in nic_to_vm and ip.get("ip"):
            ips_by_vm.setdefault(nic_to_vm[nic_id], []).append(ip["ip"])
    for v in vms:
        v["public_ip"] = ", ".join(ips_by_vm.get(v["id"], []))
    return vms


register_list_get(
    vm,
    list_fn="list_vms",
    get_fn="get_vm",
    default_columns=("name", "status", "instance_type", "public_ip"),
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
    transform=_attach_public_ips,
)


@vm.command("get", help="Get a single VM with attached disks, NICs, and IPs.")
@click.argument("name_or_id")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--query",
    default=None,
    help="Comma-separated list of columns to display (overrides defaults).",
)
@click.pass_obj
def vm_get(app: AppContext, name_or_id: str, fmt: str, query: str | None) -> None:
    vm_id = app.resolver.resolve("list_vms", name_or_id)
    vm_data = app.client.get_vm(vm_id)

    block_storages = app.client.list_block_storages(attached_machine_id=vm_id)
    nics = app.client.list_nics(attached_machine_id=vm_id)

    public_ips: list[dict] = []
    if nics:
        nic_ids = {n["id"] for n in nics}
        for ip in app.client.list_public_ips():
            if ip.get("attached_network_interface_id") in nic_ids:
                public_ips.append(ip)

    if fmt == "json":
        emit_action_result(
            {
                **vm_data,
                "attached_block_storages": block_storages,
                "attached_nics": nics,
                "attached_public_ips": public_ips,
            }
        )
        return

    render_one(vm_data, fmt=fmt, query=query, resolver=app.resolver)

    if block_storages:
        console.print()
        console.print("[bold]Attached block storages[/bold]")
        render_list(
            block_storages,
            default_columns=("name", "size_gib", "status"),
            fmt=fmt,
            query=None,
            resolver=app.resolver,
        )

    if nics:
        console.print()
        console.print("[bold]Attached NICs[/bold]")
        render_list(
            nics,
            default_columns=("name", "ip", "mac", "attached_subnet", "status"),
            fmt=fmt,
            query=None,
            resolver=app.resolver,
        )

    if public_ips:
        console.print()
        console.print("[bold]Attached public IPs[/bold]")
        render_list(
            public_ips,
            default_columns=("ip", "status"),
            fmt=fmt,
            query=None,
            resolver=app.resolver,
        )


@vm.command("create", help="Create a VM (without disk/NIC/IP — see `launch`).")
@click.option("--name", required=True)
@click.option(
    "--instance-type",
    "instance_type",
    default=None,
    help="Instance type name or UUID (e.g. 'M-8').",
)
@click.option(
    "--price-type",
    "price_type",
    type=click.Choice([t.value for t in PriceType]),
    default=None,
    help="Price type for --instance-type (default: ondemand).",
)
@click.option(
    "--pricing-id",
    "pricing_id",
    default=None,
    help="Explicit pricing UUID. With --instance-type/--price-type, all three must agree.",
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
    instance_type: str | None,
    price_type: str | None,
    pricing_id: str | None,
    username: str,
    password: str,
    always_on: bool,
    dr: bool,
    on_init_script: str,
) -> None:
    final_pricing_id, final_it_id = resolve_create_pricing(
        app,
        instance_type=instance_type,
        price_type=price_type,
        pricing_id=pricing_id,
    )

    emit_action_result(
        app.client.create_vm(
            name=name,
            instance_type_id=final_it_id,
            pricing_id=final_pricing_id,
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
    "delete",
    help=(
        "Delete a VM. Pass --cascade to also delete attached disks/NICs/IPs "
        "(disk data is destroyed)."
    ),
)
@click.argument("name_or_id")
@click.option(
    "--cascade/--no-cascade",
    default=False,
    show_default=True,
    help="Also delete attached disks, NICs, and public IPs.",
)
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.pass_obj
def vm_delete(app: AppContext, name_or_id: str, cascade: bool, yes: bool) -> None:
    vm_id = app.resolver.resolve("list_vms", name_or_id)

    disks = app.client.list_block_storages(attached_machine_id=vm_id)
    nics = app.client.list_nics(attached_machine_id=vm_id)
    nic_ids = {n["id"] for n in nics}
    ips = [
        ip
        for ip in app.client.list_public_ips(attached_network_interface_id="notnull")
        if ip.get("attached_network_interface_id") in nic_ids
    ]
    has_attached = bool(disks or nics or ips)
    will_cascade = cascade

    if has_attached and not cascade:
        parts = []
        if disks:
            parts.append(f"{len(disks)} block_storage(s)")
        if nics:
            parts.append(f"{len(nics)} NIC(s)")
        if ips:
            parts.append(f"{len(ips)} public IP(s)")
        attached_summary = ", ".join(parts)

        if yes or not _is_tty():
            raise click.ClickException(
                f"VM {name_or_id} has attached resources ({attached_summary}). "
                "Re-run with --cascade to delete them along with the VM, "
                "or detach them first."
            )
        click.echo(f"VM {name_or_id} has attached resources: {attached_summary}.")
        will_cascade = True

    if will_cascade and has_attached:
        msg = (
            f"Cascade will delete: {len(disks)} disk(s), "
            f"{len(nics)} NIC(s), {len(ips)} public IP(s). "
            "Disk data will be permanently destroyed."
        )
        if yes:
            click.echo(msg, err=True)
        else:
            click.echo(msg)

    if not yes:
        prompt = (
            f"Delete VM {name_or_id} and its attached resources?"
            if will_cascade and has_attached
            else f"Delete VM {name_or_id}?"
        )
        if not click.confirm(prompt, default=False):
            click.echo("delete cancelled; nothing was deleted.", err=True)
            raise click.exceptions.Exit(1)

    if will_cascade:
        active = next(
            (
                a
                for a in app.client.list_allocations(machine_id=vm_id)
                if is_active_allocation(a)
            ),
            None,
        )
        if active:
            click.echo(f"Stopping {name_or_id}...")
            app.client.delete_allocation(active["id"])
            click.echo("Waiting for VM to become idle...")
            app.client.wait_for_status(
                lambda: app.client.get_vm(vm_id),
                {VMStatus.idle},
                timeout=300,
                interval=3,
            )

        for ip in ips:
            app.client.attach_public_ip(ip["id"], None)
            app.client.delete_public_ip(ip["id"])

        for nic in nics:
            app.client.attach_nic(nic["id"], None)
            app.client.delete_nic(nic["id"])

        for bs in disks:
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
        if is_active_allocation(a):
            emit_action_result(app.client.delete_allocation(a["id"]))
            return

    raise click.ClickException("all allocations already terminated")
