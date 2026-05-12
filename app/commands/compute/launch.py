from __future__ import annotations

import datetime as _dt
import sys
import uuid as _uuid
from functools import partial
from typing import Any, Callable

import click

from ...client import (
    BlockStorageStatus,
    ECIError,
    PricingResourceKind,
    VMAllocationStatus,
    VMStatus,
    is_active_allocation,
)
from ...config import Config
from ...utils import AppContext, emit_action_result
from ._pricing import PriceType, resolve_create_pricing


def _is_tty() -> bool:
    return sys.stdin.isatty()


def _prompt_or_default(label: str, default: Any, *, type: Any = None) -> Any:
    """Prompt with default in a TTY; silently apply default otherwise.

    Mirrors `click.prompt(label, default=...)` but skips the prompt for
    non-interactive callers where stdin EOF would otherwise abort the
    command.
    """
    if _is_tty():
        return click.prompt(label, default=default, type=type)
    return default


def _require_in_non_tty(label: str, flag: str) -> None:
    """Raise an actionable UsageError when a required field is missing
    in a non-interactive context.

    Use this in place of click.prompt() for fields that have no safe
    default (e.g. --password). UsageError exits 2 (CLI usage convention)."""
    raise click.UsageError(
        f"--{flag} is required in non-interactive mode "
        f"(stdin is not a TTY).\n"
        f"  Pass --{flag} <{label}>, or run in an interactive terminal."
    )


def _well_known_pricing_id(app: AppContext, *, kind: str, name: str) -> str:
    return app.client.find_pricing(
        name=name, pricing_type="ondemand", resource_kind=kind
    )["id"]


DEFAULT_VNET_NAME = "eci-default-vnet"
DEFAULT_VNET_CIDR = "192.168.0.0/16"
DEFAULT_SUBNET_NAME = "eci-default-subnet"
DEFAULT_SUBNET_GATEWAY = "192.168.0.1/24"


def _list_named(items: list[dict], target_name: str) -> list[dict]:
    """Filter list_* results to those whose `name` field exactly matches."""
    return [i for i in items if i.get("name") == target_name]


def _oldest(items: list[dict]) -> dict:
    """Pick the earliest-created row. Backend rows include an ISO-8601
    `created` timestamp; lexicographic sort on that string sorts ascending
    by time. Falls back to id-sort if `created` is missing."""
    return min(items, key=lambda i: (i.get("created", ""), i.get("id", "")))


def _pick_existing_default(
    app: AppContext,
    target_name: str,
    list_fn,
    *,
    kind: str,
) -> dict | None:
    """Return the canonical row for a default-named resource, or None.

    If multiple rows exist (e.g. two concurrent `launch` calls each created
    one), pick the oldest and warn the user about the duplicates so they
    can clean up. We don't auto-delete: the duplicates may have been
    intentionally created and silently destroying them would be hostile.
    """
    candidates = _list_named(list_fn(name_ilike=target_name), target_name)
    if not candidates:
        return None

    chosen = _oldest(candidates) if len(candidates) > 1 else candidates[0]
    if len(candidates) > 1:
        extras = [c["id"] for c in candidates if c["id"] != chosen["id"]]
        click.echo(
            f"warning: {len(candidates)} {kind}s named {target_name!r} exist; "
            f"using oldest ({chosen['id']}). "
            f"Consider deleting duplicates: {', '.join(extras)}",
            err=True,
        )
    return chosen


def _ensure_default_subnet(app: AppContext) -> str:
    """Return id of `eci-default-subnet`, creating vnet+subnet if missing.

    Robust against:
      - Concurrent first-launch calls each racing to create the default
        subnet (detected post-create; oldest wins, others get a warning).
      - Orphan subnet whose attached vnet was deleted out from under it
        (raises a clear error rather than letting NIC creation fail with
        a cryptic server-side message later).
    """
    existing = _pick_existing_default(
        app, DEFAULT_SUBNET_NAME, app.client.list_subnets, kind="subnet"
    )
    if existing is not None:
        # Verify the attached vnet is still alive. If it isn't, the user
        # likely deleted vnet by hand; the subnet is orphaned and NIC
        # creation against it will fail later with a confusing error.
        attached_vnet = existing.get("attached_network_id")
        if attached_vnet:
            try:
                app.client.get_vnet(attached_vnet)
            except ECIError as e:
                if getattr(e, "status", None) == 404:
                    raise click.ClickException(
                        f"default subnet {existing['id']} references missing "
                        f"vnet {attached_vnet}. The subnet is orphaned — delete it "
                        f"and re-run:\n"
                        f"  eci network subnet delete {existing['id']}"
                    ) from None
                raise
        return existing["id"]

    existing_vnet = _pick_existing_default(
        app, DEFAULT_VNET_NAME, app.client.list_vnets, kind="vnet"
    )
    vnet_id: str
    if existing_vnet is not None:
        vnet_id = existing_vnet["id"]
    else:
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
    created = app.client.create_subnet(
        name=DEFAULT_SUBNET_NAME,
        attached_network_id=vnet_id,
        network_gw=DEFAULT_SUBNET_GATEWAY,
    )

    # Race check: another concurrent `launch` might have created its own
    # `eci-default-subnet` between our list-empty check and our create.
    # If we now see >1, defer to the oldest so future calls converge.
    post_check = _list_named(
        app.client.list_subnets(name_ilike=DEFAULT_SUBNET_NAME),
        DEFAULT_SUBNET_NAME,
    )
    if len(post_check) > 1:
        chosen = _oldest(post_check)
        extras = [s["id"] for s in post_check if s["id"] != chosen["id"]]
        click.echo(
            f"warning: detected concurrent default-subnet creation "
            f"({len(post_check)} subnets named {DEFAULT_SUBNET_NAME!r}); "
            f"using oldest ({chosen['id']}). "
            f"Consider deleting duplicates: {', '.join(extras)}",
            err=True,
        )
        return chosen["id"]

    return created["id"]


@click.command(
    "launch",
    help=(
        "Launch a VM end-to-end (VM + disk + NIC + IP + start).\n"
        "\n"
        "\b\n"
        "Required: --password.\n"
        "\n"
        "Other launch fields use sensible defaults. In a terminal they\n"
        "prompt with the default pre-filled; for non-interactive callers\n"
        "the default is applied silently (except --name, which must be\n"
        "passed explicitly). For CPU instance types (C-/M-) the default\n"
        "image is Ubuntu 24.04 LTS (Standard) with 20 GiB; for GPU/NPU\n"
        "instance types (G-/N-) the default is Ubuntu 24.04 LTS (AI/GPU)\n"
        "with 50 GiB (NVIDIA drivers + CUDA pre-installed).\n"
        "\n"
        "If --subnet is omitted, a default vnet/subnet ('eci-default-vnet' /\n"
        "'eci-default-subnet') is created on first use and reused after.\n"
        "\n"
        "OS login user defaults to 'ubuntu' (override with --username).\n"
        "\n"
        "If a vm-spec named 'default' has been saved (see `eci vm-spec save -h`),\n"
        "it is auto-applied. Explicit launch flags override individual fields;\n"
        "pass --no-spec to skip auto-apply. A 'using vm-spec ...' line is\n"
        "printed whenever spec fields are applied.\n"
        "\n"
        "`launch` returns as soon as the start request is accepted; pass\n"
        "--wait to block until the VM reaches 'started'.\n"
        "\n"
        "\b\n"
        "Password rules (enforced by the API):\n"
        "  - 3+ character classes (upper/lower/digit/special)\n"
        "  - no 3+ char ascending/descending sequence (1234, 9876, abcd ...)\n"
        "\n"
        "\b\n"
        "Examples:\n"
        "  # Easiest — every field prompted with a default\n"
        "  eci compute vm launch\n"
        "\n"
        "\b\n"
        "  # Fully non-interactive\n"
        "  eci compute vm launch --name vm-1 \\\n"
        "      --instance-type C-2 --image 'Ubuntu 24.04 LTS (Standard)' \\\n"
        "      --size-gib 20 --password 'Vk7m@p2qLn5!'\n"
        "\n"
        "\b\n"
        "  # Spot price\n"
        "  eci compute vm launch --name vm-1 --price-type spot ... (other args)\n"
        "\n"
        "\b\n"
        "  # Reuse a saved spec (see `eci vm-spec save -h`)\n"
        "  eci compute vm launch --name vm-2 --spec default --password '...'\n"
        "\n"
        "\b\n"
        "  # Reuse an existing disk; create new NIC + IP\n"
        "  eci compute vm launch --name vm-3 --block-storage existing-disk \\\n"
        "      --instance-type C-2 --subnet my-subnet --password '...'\n"
    ),
)
@click.option(
    "--name",
    default=None,
    help="VM name (also used as prefix for disk/NIC). Prompted if omitted.",
)
@click.option(
    "--password",
    default=None,
    help=(
        "OS root password (required). Needs 3+ char classes and no 3+ char sequence."
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
    default="default",
    show_default=False,
    help=(
        "Saved vm-spec name. Auto-applies 'default' if one exists. "
        "Explicit launch flags override individual spec fields."
    ),
)
@click.option(
    "--no-spec",
    "no_spec",
    is_flag=True,
    help="Skip auto-applying the 'default' vm-spec.",
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
@click.option(
    "--wait",
    is_flag=True,
    help="Wait for the VM to reach 'started' before returning.",
)
@click.pass_obj
def vm_launch(
    app: AppContext,
    name: str | None,
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
    no_spec: bool,
    block_storage: str | None,
    nic_arg: str | None,
    public_ip: str | None,
    no_network: bool,
    no_public_ip: bool,
    no_start: bool,
    wait: bool,
) -> None:
    if block_storage and (size_gib is not None or image is not None):
        raise click.ClickException(
            "--block-storage conflicts with --size-gib / --image"
        )
    if nic_arg and subnet is not None:
        raise click.ClickException("--nic conflicts with --subnet")

    if not name:
        if not _is_tty():
            _require_in_non_tty("NAME", "name")
        default_name = (
            "vm-" + _dt.datetime.now().strftime("%Y%m%d") + "-" + _uuid.uuid4().hex[:6]
        )
        name = click.prompt("name", default=default_name)

    cfg = Config.load()

    if no_spec and spec_name != "default":
        raise click.ClickException("--no-spec cannot be combined with --spec")

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
    if not no_spec:
        spec_lookup = (cfg.vm_defaults or {}).get(spec_name)
        if spec_lookup is None and spec_name != "default":
            raise click.ClickException(f"no vm-spec named {spec_name!r}")
        spec = spec_lookup

    applied_from_spec: list[tuple[str, object]] = []
    if spec is not None:
        if explicit["username"] is None and spec.get("username") is not None:
            username = spec["username"]
            applied_from_spec.append(("username", username))
        if explicit["image"] is None and spec.get("image") is not None:
            image = spec["image"]
            applied_from_spec.append(("image", image))
        if explicit["size_gib"] is None and spec.get("size_gib") is not None:
            size_gib = spec["size_gib"]
            applied_from_spec.append(("size_gib", size_gib))
        spec_subnet = spec.get("subnet") or spec.get("subnet_id")
        if explicit["subnet"] is None and spec_subnet is not None:
            subnet = spec_subnet
            applied_from_spec.append(("subnet", subnet))
        if explicit["instance_type"] is None and spec.get("instance_type") is not None:
            instance_type = spec["instance_type"]
            applied_from_spec.append(("instance_type", instance_type))
        if explicit["price_type"] is None and spec.get("price_type") is not None:
            price_type = spec["price_type"]
            applied_from_spec.append(("price_type", price_type))
        if explicit["pricing_id"] is None and spec.get("pricing_id") is not None:
            pricing_id = spec["pricing_id"]
            applied_from_spec.append(("pricing_id", pricing_id))

    if applied_from_spec and spec_name is not None:
        fields_str = ", ".join(f"{k}={v}" for k, v in applied_from_spec)
        click.echo(
            f"using vm-spec {spec_name!r}: {fields_str}\n"
            "  (override with explicit flags; pass --no-spec to skip)",
            err=True,
        )

    username = username or "ubuntu"

    if not block_storage:
        if not instance_type and not pricing_id:
            instance_type = _prompt_or_default("instance type", default="C-2")

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
            image = _prompt_or_default("image", default=default_image)
        if size_gib is None:
            default_size = 50 if wants_accelerator else 20
            size_gib = _prompt_or_default(
                "root disk size (GiB)", default=default_size, type=int
            )

    if not password:
        if not _is_tty():
            _require_in_non_tty("PASSWORD", "password")
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

    if not no_start and not no_network and not no_public_ip:
        raw_start = out.get("start")
        start_info: dict = raw_start if isinstance(raw_start, dict) else {}
        alloc_id = start_info.get("id")
        final_status: str = start_info.get("status") or "queued"

        if alloc_id and wait:
            click.echo("\nwaiting for VM to start...", err=True)
            try:
                latest = app.client.wait_for_status(
                    lambda: app.client.get_allocation(alloc_id),
                    {VMAllocationStatus.started.value},
                    timeout=300,
                    interval=3,
                )
                final_status = latest.get("status", final_status)
            except TimeoutError:
                try:
                    final_status = app.client.get_allocation(alloc_id).get(
                        "status", final_status
                    )
                except Exception:
                    pass

        raw_pip = out.get("public_ip")
        pip_info: dict = raw_pip if isinstance(raw_pip, dict) else {}
        public_ip_value = pip_info.get("ip")
        # When user passed --public-ip <existing>, we never captured the IP
        # value. Look it up via the attached NIC so the summary is complete.
        if not public_ip_value:
            try:
                nics_for_ip = app.client.list_nics(attached_machine_id=vm_id)
                nic_ids_for_ip = {n["id"] for n in nics_for_ip}
                for ip in app.client.list_public_ips():
                    if ip.get(
                        "attached_network_interface_id"
                    ) in nic_ids_for_ip and ip.get("ip"):
                        public_ip_value = ip["ip"]
                        break
            except Exception:
                pass

        summary_fields: list[tuple[str, str]] = [
            ("name", name),
            ("status", final_status),
        ]
        if public_ip_value:
            summary_fields.append(("public_ip", public_ip_value))
        summary_fields.append(("user", username))

        key_w = max(len(k) for k, _ in summary_fields)
        click.echo("", err=True)
        for k, v in summary_fields:
            click.echo(f"  {k:<{key_w}}  {v}", err=True)

        ssh_cmd = f"eci compute ssh {name}"
        if final_status == VMAllocationStatus.started.value:
            click.echo(f"  {'SSH':<{key_w}}  {ssh_cmd}", err=True)
        else:
            click.echo(f"  {'SSH':<{key_w}}  {ssh_cmd}  (once started)", err=True)

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
        if (
            has_override
            and _is_tty()
            and click.confirm("Save these arguments as a new vm-spec?", default=False)
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
