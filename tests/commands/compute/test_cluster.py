from __future__ import annotations

from click.testing import CliRunner

from app.commands.compute.cluster import cluster


def test_cluster_create_resolves_instance_type(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [{"id": "it-uuid", "name": "M-8"}]
    mock_client.create_cluster.return_value = {"id": "c1"}

    result = CliRunner().invoke(
        cluster,
        ["create", "--name", "demo", "--instance-type", "M-8"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_cluster.call_args.kwargs
    assert kwargs["name"] == "demo"
    assert kwargs["instance_type_id"] == "it-uuid"
    assert kwargs["fabric_type"] == "infiniband"


def test_cluster_create_custom_fabric(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [{"id": "it1", "name": "M-8"}]
    mock_client.create_cluster.return_value = {"id": "c1"}

    CliRunner().invoke(
        cluster,
        [
            "create",
            "--name",
            "demo",
            "--instance-type",
            "M-8",
            "--fabric-type",
            "ethernet",
        ],
        obj=app_obj,
    )
    assert mock_client.create_cluster.call_args.kwargs["fabric_type"] == "ethernet"


def test_cluster_update_no_fields_errors(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    result = CliRunner().invoke(cluster, ["update", "demo"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_cluster_update_renames(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    mock_client.update_cluster.return_value = {"id": "c1"}

    result = CliRunner().invoke(
        cluster, ["update", "demo", "--name", "new"], obj=app_obj
    )
    assert result.exit_code == 0
    args = mock_client.update_cluster.call_args
    assert args.args[0] == "c1"
    assert args.kwargs["name"] == "new"


def test_cluster_delete_with_yes(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    mock_client.delete_cluster.return_value = {"id": "c1"}

    result = CliRunner().invoke(cluster, ["delete", "demo", "-y"], obj=app_obj)
    assert result.exit_code == 0, result.output
    mock_client.delete_cluster.assert_called_once_with("c1")


def test_cluster_delete_aborts_on_no_confirmation(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    result = CliRunner().invoke(cluster, ["delete", "demo"], input="n\n", obj=app_obj)
    assert result.exit_code != 0
    mock_client.delete_cluster.assert_not_called()


def test_cluster_start(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    mock_client.create_cluster_allocation.return_value = {"id": "a1"}

    result = CliRunner().invoke(cluster, ["start", "demo"], obj=app_obj)
    assert result.exit_code == 0, result.output
    mock_client.create_cluster_allocation.assert_called_once_with("c1")


def test_cluster_stop_deletes_active_allocation(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    mock_client.list_cluster_allocations.return_value = [
        {"id": "a-old", "terminated": True},
        {"id": "a-active", "terminated": False},
    ]
    mock_client.delete_cluster_allocation.return_value = {"id": "a-active"}

    result = CliRunner().invoke(cluster, ["stop", "demo"], obj=app_obj)
    assert result.exit_code == 0, result.output
    mock_client.delete_cluster_allocation.assert_called_once_with("a-active")


def test_cluster_stop_no_allocations_errors(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    mock_client.list_cluster_allocations.return_value = []
    result = CliRunner().invoke(cluster, ["stop", "demo"], obj=app_obj)
    assert result.exit_code != 0
    assert "no active allocation" in result.output


def test_cluster_stop_all_terminated_errors(mock_client, app_obj):
    mock_client.list_clusters.return_value = [{"id": "c1", "name": "demo"}]
    mock_client.list_cluster_allocations.return_value = [
        {"id": "a1", "terminated": True}
    ]
    result = CliRunner().invoke(cluster, ["stop", "demo"], obj=app_obj)
    assert result.exit_code != 0
    assert "already terminated" in result.output
