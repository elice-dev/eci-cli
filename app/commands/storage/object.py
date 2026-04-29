from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("object", cls=ResourceGroup, help="Object storage buckets.")
def object_storage() -> None:
    pass


register_list_get(
    object_storage,
    list_fn="list_object_storages",
    get_fn="get_object_storage",
    default_columns=("name", "size_gib", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@object_storage.command("create")
@click.option("--name", required=True)
@click.option("--size-gib", "size_gib", required=True, type=int)
@click.pass_obj
def obj_create(app: AppContext, name: str, size_gib: int) -> None:
    emit_action_result(app.client.create_object_storage(name=name, size_gib=size_gib))


@object_storage.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.option("--size-gib", "size_gib", default=None, type=int)
@click.pass_obj
def obj_update(
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
        app.client.update_object_storage(
            app.resolver.resolve("list_object_storages", name_or_id), **fields
        )
    )


@object_storage.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def obj_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    oid = app.resolver.resolve("list_object_storages", name_or_id)

    if not yes:
        click.confirm(f"Delete object storage {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_object_storage(oid))


@object_storage.group("user", cls=ResourceGroup, help="Object storage users.")
def obj_user() -> None:
    pass


register_list_get(
    obj_user,
    list_fn="list_object_users",
    get_fn="get_object_user",
    default_columns=("name", "status"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@obj_user.command("create")
@click.option("--name", required=True)
@click.pass_obj
def obj_user_create(app: AppContext, name: str) -> None:
    emit_action_result(app.client.create_object_user(name=name))


@obj_user.command("update")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.pass_obj
def obj_user_update(app: AppContext, name_or_id: str, name: str | None) -> None:
    if name is None:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_object_user(
            app.resolver.resolve("list_object_users", name_or_id), name=name
        )
    )


@obj_user.command("delete")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def obj_user_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    uid = app.resolver.resolve("list_object_users", name_or_id)

    if not yes:
        click.confirm(f"Delete object user {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_object_user(uid))


@obj_user.group("grant", cls=ResourceGroup, help="Bucket grants for an object user.")
def obj_grant() -> None:
    pass


register_list_get(
    obj_grant,
    list_fn="list_object_grants",
    get_fn="get_object_grant",
    default_columns=("object_storage", "object_storage_user", "permission"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("organization_id"),
        FilterSpec("status"),
        FilterSpec("object_storage_user_id"),
        FilterSpec("object_storage_id"),
        FilterSpec("tags"),
    ],
)


@obj_grant.command("create")
@click.option("--bucket", "bucket_arg", required=True)
@click.option("--user", "user_arg", required=True)
@click.option(
    "--permission",
    type=click.Choice(["read_only", "read_write"], case_sensitive=False),
    required=True,
)
@click.pass_obj
def grant_create(
    app: AppContext, bucket_arg: str, user_arg: str, permission: str
) -> None:
    emit_action_result(
        app.client.create_object_grant(
            object_storage_id=app.resolver.resolve("list_object_storages", bucket_arg),
            object_storage_user_id=app.resolver.resolve("list_object_users", user_arg),
            permission=permission,
        )
    )


@obj_grant.command("update")
@click.argument("grant_id")
@click.option(
    "--permission",
    type=click.Choice(["read_only", "read_write"], case_sensitive=False),
    required=True,
)
@click.pass_obj
def grant_update(app: AppContext, grant_id: str, permission: str) -> None:
    emit_action_result(app.client.update_object_grant(grant_id, permission=permission))


@obj_grant.command("delete")
@click.argument("grant_id")
@click.option("-y", "--yes", is_flag=True)
@click.pass_obj
def grant_delete(app: AppContext, grant_id: str, yes: bool) -> None:
    if not yes:
        click.confirm(f"Delete grant {grant_id}?", abort=True)

    emit_action_result(app.client.delete_object_grant(grant_id))
