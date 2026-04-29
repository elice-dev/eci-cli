from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("block", cls=ResourceGroup, help="Block storage volumes.")
def block() -> None:
    pass


register_list_get(
    block,
    list_fn="list_block_storages",
    get_fn="get_block_storage",
    default_columns=("name", "size_gib", "status", "attached_machine"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("attached_machine_id"),
        FilterSpec("image_id"),
        FilterSpec("snapshot_id"),
        FilterSpec("status"),
        FilterSpec("dr", type="bool"),
        FilterSpec("pricing_type"),
        FilterSpec("pricing_id"),
        FilterSpec("tags"),
    ],
)


@block.command("create")
@click.option("--name", required=True)
@click.option("--size-gib", "size_gib", required=True, type=int)
@click.option("--pricing", required=True)
@click.option("--image", default=None)
@click.option("--snapshot", default=None)
@click.option("--dr/--no-dr", default=False)
@click.pass_obj
def block_create(
    app: AppContext,
    name: str,
    size_gib: int,
    pricing: str,
    image: str | None,
    snapshot: str | None,
    dr: bool,
) -> None:
    if image and snapshot:
        raise click.ClickException("--image and --snapshot are mutually exclusive")

    emit_action_result(
        app.client.create_block_storage(
            name=name,
            size_gib=size_gib,
            pricing_id=app.resolver.resolve("list_pricings", pricing),
            image_id=app.resolver.resolve("list_images", image) if image else None,
            snapshot_id=(
                app.resolver.resolve("list_block_snapshots", snapshot)
                if snapshot
                else None
            ),
            dr=dr,
        )
    )


@block.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.option("--size-gib", "size_gib", default=None, type=int)
@click.pass_obj
def block_update(
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
        app.client.update_block_storage(
            app.resolver.resolve("list_block_storages", name_or_id), **fields
        )
    )


@block.command("attach")
@click.argument("name_or_id")
@click.option("--vm", "vm_arg", required=True)
@click.pass_obj
def block_attach(app: AppContext, name_or_id: str, vm_arg: str) -> None:
    emit_action_result(
        app.client.attach_block_storage(
            app.resolver.resolve("list_block_storages", name_or_id),
            app.resolver.resolve("list_vms", vm_arg),
        )
    )


@block.command("detach")
@click.argument("name_or_id")
@click.pass_obj
def block_detach(app: AppContext, name_or_id: str) -> None:
    emit_action_result(
        app.client.attach_block_storage(
            app.resolver.resolve("list_block_storages", name_or_id), None
        )
    )


@block.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def block_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    bid = app.resolver.resolve("list_block_storages", name_or_id)

    if not yes:
        click.confirm(f"Delete block storage {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_block_storage(bid))


@block.group("snapshot", cls=ResourceGroup, help="Block storage snapshots.")
def block_snapshot() -> None:
    pass


register_list_get(
    block_snapshot,
    list_fn="list_block_snapshots",
    get_fn="get_block_snapshot",
    default_columns=("name", "block_storage", "size_gib", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("block_storage_id"),
        FilterSpec("image_id"),
        FilterSpec("snapshot_scheduler_id"),
        FilterSpec("status"),
        FilterSpec("dr", type="bool"),
        FilterSpec("tags"),
    ],
)


@block_snapshot.command("create")
@click.option("--name", required=True)
@click.option("--block", "block_arg", required=True, help="block storage UUID or name")
@click.pass_obj
def snapshot_create(app: AppContext, name: str, block_arg: str) -> None:
    emit_action_result(
        app.client.create_block_snapshot(
            name=name,
            block_storage_id=app.resolver.resolve("list_block_storages", block_arg),
        )
    )


@block_snapshot.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.pass_obj
def snapshot_update(app: AppContext, name_or_id: str, name: str | None) -> None:
    if name is None:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_block_snapshot(
            app.resolver.resolve("list_block_snapshots", name_or_id), name=name
        )
    )


@block_snapshot.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def snapshot_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    sid = app.resolver.resolve("list_block_snapshots", name_or_id)

    if not yes:
        click.confirm(f"Delete snapshot {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_block_snapshot(sid))


@block.group("scheduler", cls=ResourceGroup, help="Snapshot schedulers.")
def block_scheduler() -> None:
    pass


register_list_get(
    block_scheduler,
    list_fn="list_snapshot_schedulers",
    get_fn="get_snapshot_scheduler",
    default_columns=("name", "block_storage", "cron_expression", "max_snapshots"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("block_storage_id"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@block_scheduler.command("create")
@click.option("--name", required=True)
@click.option("--block", "block_arg", required=True)
@click.option("--cron", "cron_expression", required=True)
@click.option("--max-snapshots", "max_snapshots", required=True, type=int)
@click.pass_obj
def scheduler_create(
    app: AppContext,
    name: str,
    block_arg: str,
    cron_expression: str,
    max_snapshots: int,
) -> None:
    emit_action_result(
        app.client.create_snapshot_scheduler(
            name=name,
            block_storage_id=app.resolver.resolve("list_block_storages", block_arg),
            cron_expression=cron_expression,
            max_snapshots=max_snapshots,
        )
    )


@block_scheduler.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.option("--cron", "cron_expression", default=None)
@click.option("--max-snapshots", "max_snapshots", default=None, type=int)
@click.pass_obj
def scheduler_update(
    app: AppContext,
    name_or_id: str,
    name: str | None,
    cron_expression: str | None,
    max_snapshots: int | None,
) -> None:
    fields: dict = {}

    if name is not None:
        fields["name"] = name

    if cron_expression is not None:
        fields["cron_expression"] = cron_expression

    if max_snapshots is not None:
        fields["max_snapshots"] = max_snapshots

    if not fields:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_snapshot_scheduler(
            app.resolver.resolve("list_snapshot_schedulers", name_or_id), **fields
        )
    )


@block_scheduler.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def scheduler_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    sid = app.resolver.resolve("list_snapshot_schedulers", name_or_id)

    if not yes:
        click.confirm(f"Delete scheduler {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_snapshot_scheduler(sid))
