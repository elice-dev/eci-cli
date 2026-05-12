from __future__ import annotations

import os
import shutil

import click

from ...utils import AppContext


@click.command(
    "ssh",
    help=(
        "SSH into a VM via its attached public IP.\n"
        "\n"
        "\b\n"
        "Anything after NAME_OR_ID is forwarded to ssh, after the destination.\n"
        "Use this to run a remote command:\n"
        "\n"
        "\b\n"
        "  eci compute ssh vm-1 echo hello\n"
        "  eci compute ssh vm-1 -- ls /var/log\n"
    ),
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("name_or_id")
@click.option(
    "-l",
    "--login",
    "login",
    default=None,
    help="SSH login user (defaults to the VM's stored username).",
)
@click.option("-p", "--port", default=None, type=int, help="SSH port.")
@click.option("-i", "--identity", default=None, help="SSH identity file.")
@click.argument("ssh_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def vm_ssh(
    app: AppContext,
    name_or_id: str,
    login: str | None,
    port: int | None,
    identity: str | None,
    ssh_args: tuple[str, ...],
) -> None:
    if shutil.which("ssh") is None:
        raise click.ClickException("`ssh` not found on PATH")

    vm_id = app.resolver.resolve("list_vms", name_or_id)
    vm_data = app.client.get_vm(vm_id)
    user = login or vm_data.get("username") or "ubuntu"

    nics = app.client.list_nics(attached_machine_id=vm_id)
    if not nics:
        raise click.ClickException(f"VM {name_or_id} has no NIC attached")

    nic_ids = {n["id"] for n in nics}
    pip = next(
        (
            ip
            for ip in app.client.list_public_ips()
            if ip.get("attached_network_interface_id") in nic_ids and ip.get("ip")
        ),
        None,
    )
    if pip is None:
        raise click.ClickException(f"VM {name_or_id} has no public IP attached")

    cmd = ["ssh"]
    if port is not None:
        cmd += ["-p", str(port)]
    if identity:
        cmd += ["-i", identity]
    cmd.append(f"{user}@{pip['ip']}")
    cmd += list(ssh_args)

    os.execvp("ssh", cmd)
