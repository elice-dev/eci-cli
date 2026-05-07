from __future__ import annotations

import click

from ...utils import (
    AppContext,
    FilterSpec,
    ResourceGroup,
    emit_action_result,
    register_list_get,
)


@click.group("cluster", cls=ResourceGroup, help="Virtual clusters.")
def cluster() -> None:
    pass


register_list_get(
    cluster,
    list_fn="list_clusters",
    get_fn="get_cluster",
    default_columns=("name", "instance_type"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("organization_id"),
        FilterSpec("instance_type_id"),
        FilterSpec("status"),
        FilterSpec("tags"),
    ],
)


@cluster.command("create", help="Create a virtual cluster.")
@click.option("--name", required=True)
@click.option(
    "--instance-type",
    "instance_type",
    required=True,
    help="Instance type name or UUID.",
)
@click.option("--fabric-type", "fabric_type", default="infiniband", show_default=True)
@click.pass_obj
def cluster_create(
    app: AppContext, name: str, instance_type: str, fabric_type: str
) -> None:
    emit_action_result(
        app.client.create_cluster(
            name=name,
            instance_type_id=app.resolver.resolve("list_instance_types", instance_type),
            fabric_type=fabric_type,
        )
    )


@cluster.command("update", help="Rename a cluster.")
@click.argument("name_or_id")
@click.option("--name", default=None)
@click.pass_obj
def cluster_update(app: AppContext, name_or_id: str, name: str | None) -> None:
    if name is None:
        raise click.ClickException("nothing to update")

    emit_action_result(
        app.client.update_cluster(
            app.resolver.resolve("list_clusters", name_or_id), name=name
        )
    )


@cluster.command("delete", help="Delete a cluster.")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.pass_obj
def cluster_delete(app: AppContext, name_or_id: str, yes: bool) -> None:
    cid = app.resolver.resolve("list_clusters", name_or_id)

    if not yes:
        click.confirm(f"Delete cluster {name_or_id}?", abort=True)

    emit_action_result(app.client.delete_cluster(cid))


@cluster.command("start", help="Boot a cluster (create allocation).")
@click.argument("name_or_id")
@click.pass_obj
def cluster_start(app: AppContext, name_or_id: str) -> None:
    emit_action_result(
        app.client.create_cluster_allocation(
            app.resolver.resolve("list_clusters", name_or_id)
        )
    )


@cluster.command("stop", help="Stop a cluster (delete current allocation).")
@click.argument("name_or_id")
@click.pass_obj
def cluster_stop(app: AppContext, name_or_id: str) -> None:
    allocs = app.client.list_cluster_allocations(
        cluster_id=app.resolver.resolve("list_clusters", name_or_id)
    )

    if not allocs:
        raise click.ClickException("cluster has no active allocation")

    for a in allocs:
        if not a.get("terminated"):
            emit_action_result(app.client.delete_cluster_allocation(a["id"]))
            return

    raise click.ClickException("all cluster allocations already terminated")
