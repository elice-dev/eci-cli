from __future__ import annotations

from functools import partial
from typing import Any, Callable

import click

from ...client import (
    BlockStorageStatus,
    PricingResourceKind,
    VMStatus,
    is_active_allocation,
)
from ...config import Config
from ...utils import AppContext, emit_action_result
from ._pricing import PriceType, resolve_create_pricing


def _well_known_pricing_id(app: AppContext, *, kind: str, name: str) -> str:
    return app.client.find_pricing(
        name=name, pricing_type="ondemand", resource_kind=kind
    )["id"]


DEFAULT_VNET_NAME = "eci-default-vnet"
DEFAULT_VNET_CIDR = "192.168.0.0/16"
DEFAULT_SUBNET_NAME = "eci-default-subnet"
DEFAULT_SUBNET_GATEWAY = "192.168.0.1/24"


def _ensure_default_subnet(app: AppContext) -> str:
    """Return id of `eci-default-subnet`, creating vnet+subnet if missing.

    Idempotent: re-uses an existing default vnet/subnet when present so
    repeated `vm launch` calls don't pile up resources.
    """
    existing_subnets = app.client.list_subnets(name_ilike=DEFAULT_SUBNET_NAME)
    for s in existing_subnets:
        if s.get("name") == DEFAULT_SUBNET_NAME:
            return s["id"]

    existing_vnets = app.client.list_vnets(name_ilike=DEFAULT_VNET_NAME)
    vnet_id: str | None = None
    for v in existing_vnets:
        if v.get("name") == DEFAULT_VNET_NAME:
            vnet_id = v["id"]
            break

    if vnet_id is None:
        click.echo(
            f"creating default vnet '{DEFAULT_VNET_NAME}' ({DEFAULT_VNET_CIDR})",
            err=True,
        )
        vnet_id = app.client.create_vnet(
            name=DEFAULT_VNET_NAME, network_cidr=DEFAULT_VNET_CIDR
        )["id"]

    click.echo(
        f"creating default subnet '{DEFAULT_SUBNET_NAME}' ({DEFAULT_SUBNET_GATEWAY})",
        err=True,
    )
    return app.client.create_subnet(
        name=DEFAULT_SUBNET_NAME,
        attached_network_id=vnet_id,
        network_gw=DEFAULT_SUBNET_GATEWAY,
    )["id"]


@click.command(
    "launch",
    help=(
        "Launch a VM end-to-end (VM + disk + NIC + IP + start).\n"
        "\n"
        "\b\n"
        "Required: --name. Other launch fields are prompted with sensible\n"
        "defaults if not passed. For CPU instance types (C-/M-) the default\n"
        "image is Ubuntu 24.04 LTS (Standard) with 20 GiB; for GPU/NPU\n"
        "instance types (G-/N-) the default is Ubuntu 24.04 LTS (AI/GPU)\n"
        "with 50 GiB (NVIDIA drivers + CUDA pre-installed).\n"
        "\n"
        "If --subnet is omitted, a default vnet/subnet ('eci-default-vnet' /\n"
        "'eci-default-subnet') is created on first use and reused after.\n"
        "\n"
        "\b\n"
        "Password rules (enforced by the API):\n"
        "  - 3+ character classes (upper/lower/digit/special)\n"
        "  - no 3+ char ascending/descending sequence (1234, 9876, abcd ...)\n"
        "\n"
        "\b\n"
        "Examples:\n"
        "  # Easiest — only --name; everything else prompted with defaults\n"
        "  eci compute vm launch --name web-1\n"
        "\n"
        "\b\n"
        "  # Fully non-interactive\n"
        "  eci compute vm launch --name web-1 \\\n"
        "      --instance-type C-2 --image 'Ubuntu 24.04 LTS (Standard)' \\\n"
        "      --size-gib 20 --password 'Vk7m@p2qLn5!'\n"
        "\n"
        "\b\n"
        "  # Spot price\n"
        "  eci compute vm launch --name web-1 --price-type spot ... (other args)\n"
        "\n"
        "\b\n"
        "  # Reuse a saved spec (see `eci vm-spec save -h`)\n"
        "  eci compute vm launch --name web-2 --spec default --password '...'\n"
        "\n"
        "\b\n"
        "  # Reuse an existing disk; create new NIC + IP\n"
        "  eci compute vm launch --name web-3 --block-storage existing-disk \\\n"
        "      --instance-type C-2 --subnet my-subnet --password '...'\n"
    ),
)
@click.option(
    "--name", required=True, help="VM name (also used as prefix for disk/NIC)."
)
@click.option(
    "--password",
    default=None,
    help=(
        "OS root password. Required unless --no-start. "
        "Needs 3+ char classes and no 3+ char sequence."
    ),
)
@click.option(
    "--username", default=None, help="OS first user (default: ubuntu or from spec)."
)
@click.option(
    "--instance-type",
    "instance_type",
    default=None,
    help="Instance type name or UUID (e.g. 'C-2'). See `eci instance-type`.",
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
@click.option(
    "--image",
    default=None,
    help="OS image name or UUID (e.g. 'Ubuntu 24.04 LTS (Standard)'). See `eci image`.",
)
@click.option(
    "--size-gib",
    "size_gib",
    type=int,
    default=None,
    help="Root disk size in GiB (e.g. 20).",
)
@click.option(
    "--subnet",
    default=None,
    help="Subnet name or UUID. See `eci network subnet`.",
)
@click.option(
    "--init-script",
    default="",
    help="Shell snippet to run on first boot.",
)
@click.option(
    "--always-on/--no-always-on",
    default=False,
    help="Auto-restart on host crash / DR event.",
)
@click.option(
    "--dr/--no-dr",
    default=False,
    help="Enable disaster-recovery replication for the VM and root disk.",
)
@click.option(
    "--spec",
    "spec_name",
    is_flag=False,
    flag_value="default",
    default=None,
    help="Use a saved vm-spec by name (default = `default`).",
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
    instance_type: str | None,
    price_type: str | None,
    pricing_id: str | None,
    image: str | None,
    size_gib: int | None,
    subnet: str | None,
    init_script: str,
    always_on: bool,
    dr: bool,
    spec_name: str | None,
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
    explicit = {
        "username": username,
        "instance_type": instance_type,
        "price_type": price_type,
        "pricing_id": pricing_id,
        "image": image,
        "size_gib": size_gib,
        "subnet": subnet,
    }
    spec: dict | None = None
    if spec_name:
        spec = (cfg.vm_defaults or {}).get(spec_name)
        if not spec:
            raise click.ClickException(f"no vm-spec named {spec_name!r}")
        username = username or spec.get("username")
        image = image if image is not None else spec.get("image")
        size_gib = size_gib if size_gib is not None else spec.get("size_gib")
        subnet = subnet or spec.get("subnet") or spec.get("subnet_id")
        instance_type = instance_type or spec.get("instance_type")
        price_type = price_type or spec.get("price_type")
        pricing_id = pricing_id or spec.get("pricing_id")

    username = username or "ubuntu"

    if not block_storage:
        if not instance_type and not pricing_id:
            instance_type = click.prompt("instance type", default="C-2")

        # Pick image/size defaults based on whether the chosen instance type
        # has accelerators — GPU/NPU types need the AI/GPU image (NVIDIA
        # drivers + CUDA pre-installed), CPU types get the lighter Standard.
        wants_accelerator = False
        if instance_type and not image:
            try:
                its = app.client.list_instance_types(name_ilike=instance_type)
                match = next(
                    (it for it in its if it.get("name") == instance_type), None
                )
                if match and match.get("devices"):
                    wants_accelerator = True
            except Exception:
                pass

        if not image:
            default_image = (
                "Ubuntu 24.04 LTS (AI/GPU)"
                if wants_accelerator
                else "Ubuntu 24.04 LTS (Standard)"
            )
            image = click.prompt("image", default=default_image)
        if size_gib is None:
            default_size = 50 if wants_accelerator else 20
            size_gib = click.prompt(
                "root disk size (GiB)", default=default_size, type=int
            )

    if not password:
        click.echo(
            "password (3+ char classes, no 3+ char sequence)",
            err=True,
        )
        password = click.prompt("password", hide_input=True, confirmation_prompt=False)

    if not block_storage:
        if size_gib is None:
            raise click.ClickException(
                "--size-gib is required (or use --block-storage)"
            )

        if not image:
            raise click.ClickException("--image is required (or use --block-storage)")

    if not no_network and not nic_arg and not subnet:
        subnet = _ensure_default_subnet(app)

    out: dict[str, Any] = {}
    cleanups: list[tuple[str, Callable[[], Any]]] = []

    def _rollback() -> None:
        if not cleanups:
            return
        click.echo(
            f"launch failed; rolling back {len(cleanups)} created resource(s)",
            err=True,
        )
        for desc, fn in reversed(cleanups):
            try:
                fn()
            except Exception as e:
                click.echo(f"  rollback: {desc} failed: {e}", err=True)

    try:
        vm_pricing_id, instance_type_id = resolve_create_pricing(
            app,
            instance_type=instance_type,
            price_type=price_type,
            pricing_id=pricing_id,
        )
        out["resolved"] = {
            "instance_type_id": instance_type_id,
            "pricing_id": vm_pricing_id,
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
        cleanups.append((f"delete vm {vm_id}", partial(app.client.delete_vm, vm_id)))

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
                    app, kind=PricingResourceKind.block_storage, name="Block Storage"
                ),
                image_id=app.resolver.resolve("list_images", image) if image else None,
                dr=dr,
            )
            out["block_storage"] = bs
            bs_id = bs["id"]
            cleanups.append(
                (
                    f"delete block_storage {bs_id}",
                    partial(app.client.delete_block_storage, bs_id),
                )
            )

            app.client.wait_for_status(
                lambda: app.client.get_block_storage(bs_id),
                {BlockStorageStatus.prepared},
                timeout=600,
            )

        out["block_storage_attach"] = app.client.attach_block_storage(bs_id, vm_id)
        cleanups.append(
            (
                f"detach block_storage {bs_id}",
                partial(app.client.attach_block_storage, bs_id, None),
            )
        )

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
                cleanups.append(
                    (
                        f"delete nic {nic_id}",
                        partial(app.client.delete_nic, nic_id),
                    )
                )
            out["nic_attach"] = app.client.attach_nic(nic_id, vm_id)
            cleanups.append(
                (
                    f"detach nic {nic_id}",
                    partial(app.client.attach_nic, nic_id, None),
                )
            )

            if not no_public_ip:
                if public_ip:
                    pip_id = app.resolver.resolve("list_public_ips", public_ip)
                else:
                    pip = app.client.create_public_ip(
                        pricing_id=_well_known_pricing_id(
                            app, kind=PricingResourceKind.public_ip, name="Public IP"
                        ),
                        dr=dr,
                    )
                    out["public_ip"] = pip
                    pip_id = pip["id"]
                    cleanups.append(
                        (
                            f"delete public_ip {pip_id}",
                            partial(app.client.delete_public_ip, pip_id),
                        )
                    )
                out["public_ip_attach"] = app.client.attach_public_ip(pip_id, nic_id)
                cleanups.append(
                    (
                        f"detach public_ip {pip_id}",
                        partial(app.client.attach_public_ip, pip_id, None),
                    )
                )

        if not no_start:
            alloc = app.client.create_allocation(vm_id)
            out["start"] = alloc

            if not isinstance(alloc, dict) or not alloc.get("id"):
                click.echo(
                    f"warning: create_allocation response did not include id; "
                    f"verify server-side state for vm {vm_id}",
                    err=True,
                )

            def _stop_active_and_wait_idle(vid: str = vm_id) -> None:
                for a in app.client.list_allocations(machine_id=vid):
                    if is_active_allocation(a):
                        app.client.delete_allocation(a["id"])
                app.client.wait_for_status(
                    lambda: app.client.get_vm(vid),
                    {VMStatus.idle},
                    timeout=300,
                    interval=3,
                )

            cleanups.append(
                (
                    f"stop allocation and wait for vm {vm_id} idle",
                    _stop_active_and_wait_idle,
                )
            )
    except BaseException:
        _rollback()
        raise

    emit_action_result(out)

    if spec_name and spec is not None:
        spec_subnet = spec.get("subnet") or spec.get("subnet_id")
        has_override = any(
            (
                explicit["username"] is not None
                and explicit["username"] != spec.get("username"),
                explicit["instance_type"] is not None
                and explicit["instance_type"] != spec.get("instance_type"),
                explicit["price_type"] is not None
                and explicit["price_type"] != spec.get("price_type"),
                explicit["pricing_id"] is not None
                and explicit["pricing_id"] != spec.get("pricing_id"),
                explicit["image"] is not None
                and explicit["image"] != spec.get("image"),
                explicit["size_gib"] is not None
                and explicit["size_gib"] != spec.get("size_gib"),
                explicit["subnet"] is not None and explicit["subnet"] != spec_subnet,
            )
        )
        if has_override and click.confirm(
            "Save these arguments as a new vm-spec?", default=False
        ):
            new_name = click.prompt("spec name")
            cfg.vm_defaults = cfg.vm_defaults or {}
            new_spec: dict = {
                "username": username,
                "size_gib": size_gib,
                "image": image,
                "subnet": subnet,
            }
            if instance_type is not None:
                new_spec["instance_type"] = instance_type
            if price_type is not None:
                new_spec["price_type"] = price_type
            if pricing_id is not None:
                new_spec["pricing_id"] = pricing_id
            cfg.vm_defaults[new_name] = new_spec
            cfg.save()
            click.echo(f"saved vm_defaults.{new_name}")
