from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("pfs", cls=ResourceGroup, help="Parallel file systems.")
def pfs() -> None:
    pass


register_list_get(
    pfs,
    list_fn="list_pfs",
    get_fn="get_pfs",
    default_columns=("name", "size_gib", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@pfs.command("create")
@click.option("--name", required=True)
@click.option("--size-gib", "size_gib", required=True, type=int)
@click.pass_obj
def pfs_create(app: AppContext, name: str, size_gib: int) -> None:
    emit_action_result(app.client.create_pfs(name=name, size_gib=size_gib))


@pfs.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.option("--size-gib", "size_gib", default=None, type=int)
@click.pass_obj
def pfs_update(
    app: AppContext, name_or_id: str, name: str | None, size_gib: int | None
) -> None:
    fields: dict = {}
    if name is not None:
        fields["name"] = name

    if size_gib is not None:
        fields["size_gib"] = size_gib

    if not fields:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_pfs(app.resolver.resolve("list_pfs", name_or_id), **fields)
    )


@pfs.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def pfs_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    pid = app.resolver.resolve("list_pfs", name_or_id)

    if not yes:
        click.confirm(f"Delete PFS {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_pfs(pid))


@pfs.group("member", cls=ResourceGroup, help="PFS members.")
def pfs_member() -> None:
    pass


register_list_get(
    pfs_member,
    list_fn="list_pfs_members",
    get_fn="get_pfs_member",
    default_columns=("parallel_file_system", "machine", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("machine_id"),
        FilterSpec("parallel_file_system_id"),
        FilterSpec("tags"),
    ],
)


@pfs_member.command("create")
@click.option("--pfs", "pfs_arg", required=True)
@click.option("--vm", "vm_arg", required=True)
@click.pass_obj
def pfs_member_create(app: AppContext, pfs_arg: str, vm_arg: str) -> None:
    emit_action_result(
        app.client.create_pfs_member(
            pfs_id=app.resolver.resolve("list_pfs", pfs_arg),
            machine_id=app.resolver.resolve("list_vms", vm_arg),
        )
    )


@pfs_member.command("delete")
@click.argument("member_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def pfs_member_delete(app: AppContext, member_id: str, yes: bool) -> None:
    if not yes:
        click.confirm(f"Delete PFS member {member_id}?", abort=True)

    emit_action_result(app.client.delete_pfs_member(member_id))
