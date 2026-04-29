from __future__ import annotations

from click.testing import CliRunner

from app.commands.network.subnet import subnet


def test_subnet_create_resolves_vnet_name(mock_client, app_obj):
    mock_client.list_vnets.return_value = [{"id": "v-uuid", "name": "main"}]
    mock_client.create_subnet.return_value = {"id": "s1"}

    result = CliRunner().invoke(
        subnet,
        ["create", "--name", "s", "--network", "main", "--gateway", "10.0.0.1"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_subnet.call_args.kwargs
    assert kwargs["attached_network_id"] == "v-uuid"
    assert kwargs["purpose"] == "virtual_machine"


def test_subnet_update_renames(mock_client, app_obj):
    mock_client.list_subnets.return_value = [{"id": "s1", "name": "s"}]
    mock_client.update_subnet.return_value = {"id": "s1"}
    result = CliRunner().invoke(
        subnet, ["update", "s", "--name", "new"], obj=app_obj
    )
    assert result.exit_code == 0
    assert mock_client.update_subnet.call_args.kwargs["name"] == "new"


def test_subnet_update_no_fields_errors(mock_client, app_obj):
    mock_client.list_subnets.return_value = [{"id": "s1", "name": "s"}]
    result = CliRunner().invoke(subnet, ["update", "s"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_subnet_delete_with_yes(mock_client, app_obj):
    mock_client.list_subnets.return_value = [{"id": "s1", "name": "s"}]
    mock_client.delete_subnet.return_value = {"id": "s1"}
    result = CliRunner().invoke(subnet, ["delete", "s", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_subnet.assert_called_once_with("s1")
