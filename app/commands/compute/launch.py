from __future__ import annotations

from typing import Any

import click

from ...config import Config
from ...utils import AppContext, emit_action_result


def _well_known_pricing_id(app: AppContext, *, kind: str, name: str) -> str:
    return app.client.find_pricing(
        name=name, pricing_type="ondemand", resource_kind=kind
    )["id"]


@click.command("launch", help="Launch a VM end-to-end (VM + disk + NIC + IP + start).")
@click.option(
    "--name", required=True, help="VM name (also used as prefix for disk/NIC)."
)
@click.option("--password", default=None, help="OS root password.")
@click.option(
    "--username", default=None, help="OS first user (default: ubuntu or from spec)."
)
@click.option(
    "--pricing",
    default=None,
    help="VM pricing name (e.g. 'M-8'). Determines the instance type.",
)
@click.option("--image", default=None, help="OS image name or UUID.")
@click.option("--size-gib", "size_gib", type=int, default=None)
@click.option("--subnet", default=None, help="Subnet UUID or name.")
@click.option("--init-script", default="")
@click.option("--always-on/--no-always-on", default=False)
@click.option("--dr/--no-dr", default=False)
@click.option(
    "--defined",
    "defined",
    is_flag=False,
    flag_value="default",
    default=None,
    help="Use a saved spec from vm_defaults (default name = `default`).",
)
@click.option(
    "--block-storage",
    "block_storage",
    default=None,
    help="Reuse existing block storage.",
)
@click.option("--nic", "nic_arg", default=None, help="Reuse existing NIC.")
@click.option(
    "--public-ip", "public_ip", default=None, help="Reuse existing public IP."
)
@click.option("--no-network", is_flag=True, help="Skip NIC + public IP.")
@click.option("--no-public-ip", is_flag=True, help="Create NIC but skip public IP.")
@click.option("--no-start", is_flag=True, help="Skip the boot step.")
@click.pass_obj
def vm_launch(
    app: AppContext,
    name: str,
    password: str | None,
    username: str | None,
    pricing: str | None,
    image: str | None,
    size_gib: int | None,
    subnet: str | None,
    init_script: str,
    always_on: bool,
    dr: bool,
    defined: str | None,
    block_storage: str | None,
    nic_arg: str | None,
    public_ip: str | None,
    no_network: bool,
    no_public_ip: bool,
    no_start: bool,
) -> None:
    if block_storage and (size_gib is not None or image is not None):
        raise click.ClickException(
            "--block-storage conflicts with --size-gib / --image"
        )
    if nic_arg and subnet is not None:
        raise click.ClickException("--nic conflicts with --subnet")

    cfg = Config.load()
    if defined:
        spec = (cfg.vm_defaults or {}).get(defined)
        if not spec:
            raise click.ClickException(f"no vm_defaults spec named {defined!r}")
        username = username or spec.get("username")
        image = image if image is not None else spec.get("image")
        size_gib = size_gib if size_gib is not None else spec.get("size_gib")
        subnet = subnet or spec.get("subnet") or spec.get("subnet_id")
        pricing = pricing or spec.get("pricing")

    username = username or "ubuntu"

    if not password:
        password = click.prompt("password", hide_input=True, confirmation_prompt=False)

    if not pricing:
        raise click.ClickException("--pricing is required")

    if not block_storage:
        if size_gib is None:
            raise click.ClickException(
                "--size-gib is required (or use --block-storage)"
            )

        if not image:
            raise click.ClickException("--image is required (or use --block-storage)")

    if not no_network and not nic_arg and not subnet:
        raise click.ClickException(
            "--subnet is required (or pass --nic / --no-network)"
        )

    out: dict[str, Any] = {}

    vm_pricing_id = app.resolver.resolve("list_pricings", pricing)
    vm_pricing_obj = app.client.get_pricing(vm_pricing_id)

    if vm_pricing_obj.get("resource_kind") != "vm_allocation" or not vm_pricing_obj.get(
        "resource_id"
    ):
        raise click.ClickException(
            f"pricing {pricing!r} is not a VM pricing "
            f"(resource_kind={vm_pricing_obj.get('resource_kind')!r})"
        )

    instance_type_id = vm_pricing_obj["resource_id"]
    out["resolved"] = {
        "instance_type_id": instance_type_id,
        "image": image,
    }

    vm_obj = app.client.create_vm(
        name=name,
        instance_type_id=instance_type_id,
        pricing_id=vm_pricing_id,
        username=username,
        password=password,
        always_on=always_on,
        dr=dr,
        on_init_script=init_script,
    )
    out["vm"] = vm_obj
    vm_id = vm_obj["id"]

    if block_storage:
        bs_id = app.resolver.resolve("list_block_storages", block_storage)
    else:
        if size_gib is None:
            raise click.ClickException(
                "--size-gib is required (or use --block-storage)"
            )
        bs = app.client.create_block_storage(
            name=f"{name}-disk",
            size_gib=size_gib,
            pricing_id=_well_known_pricing_id(
                app, kind="block_storage", name="Block Storage"
            ),
            image_id=app.resolver.resolve("list_images", image) if image else None,
            dr=dr,
        )
        out["block_storage"] = bs
        bs_id = bs["id"]

        app.client.wait_for_status(
            lambda: app.client.get_block_storage(bs_id), {"prepared"}, timeout=600
        )
    out["block_storage_attach"] = app.client.attach_block_storage(bs_id, vm_id)

    if not no_network:
        if nic_arg:
            nic_id = app.resolver.resolve("list_nics", nic_arg)
        else:
            if subnet is None:
                raise click.ClickException(
                    "--subnet is required (or pass --nic / --no-network)"
                )

            nic = app.client.create_nic(
                name=f"{name}-nic",
                attached_subnet_id=app.resolver.resolve("list_subnets", subnet),
                dr=dr,
            )
            out["nic"] = nic
            nic_id = nic["id"]
        out["nic_attach"] = app.client.attach_nic(nic_id, vm_id)

        if not no_public_ip:
            if public_ip:
                pip_id = app.resolver.resolve("list_public_ips", public_ip)
            else:
                pip = app.client.create_public_ip(
                    pricing_id=_well_known_pricing_id(
                        app, kind="public_ip", name="Public IP"
                    ),
                    dr=dr,
                )
                out["public_ip"] = pip
                pip_id = pip["id"]
            out["public_ip_attach"] = app.client.attach_public_ip(pip_id, nic_id)

    if not no_start:
        out["start"] = app.client.create_allocation(vm_id)

    emit_action_result(out)

    if defined:
        if any(
            v is not None for v in (pricing, image, size_gib, subnet, username)
        ) and click.confirm(
            "Save these arguments as a new vm_defaults spec?", default=False
        ):
            spec_name = click.prompt("spec name")
            cfg.vm_defaults = cfg.vm_defaults or {}
            cfg.vm_defaults[spec_name] = {
                "username": username,
                "pricing": pricing,
                "size_gib": size_gib,
                "image": image,
                "subnet": subnet,
            }
            cfg.save()
            click.echo(f"saved vm_defaults.{spec_name}")
