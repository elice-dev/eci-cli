from __future__ import annotations

from click.testing import CliRunner

from app.commands.network.nic import nic


def test_nic_create(mock_client, app_obj):
    mock_client.list_subnets.return_value = [{"id": "s-uuid", "name": "s"}]
    mock_client.create_nic.return_value = {"id": "n1"}
    result = CliRunner().invoke(
        nic, ["create", "--name", "n", "--subnet", "s", "--ip", "10.0.0.5"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_nic.call_args.kwargs
    assert kwargs["attached_subnet_id"] == "s-uuid"
    assert kwargs["ip"] == "10.0.0.5"
    assert kwargs["dr"] is False


def test_nic_attach(mock_client, app_obj):
    mock_client.list_nics.return_value = [{"id": "nic-1", "name": "n"}]
    mock_client.list_vms.return_value = [{"id": "vm-1", "name": "vm"}]
    mock_client.attach_nic.return_value = {"ok": True}

    result = CliRunner().invoke(
        nic, ["attach", "n", "--vm", "vm"], obj=app_obj
    )
    assert result.exit_code == 0
    mock_client.attach_nic.assert_called_once_with("nic-1", "vm-1")


def test_nic_detach(mock_client, app_obj):
    mock_client.list_nics.return_value = [{"id": "nic-1", "name": "n"}]
    mock_client.attach_nic.return_value = {"ok": True}

    result = CliRunner().invoke(nic, ["detach", "n"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.attach_nic.assert_called_once_with("nic-1", None)


def test_nic_update_no_fields(mock_client, app_obj):
    mock_client.list_nics.return_value = [{"id": "n1", "name": "n"}]
    result = CliRunner().invoke(nic, ["update", "n"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_nic_delete(mock_client, app_obj):
    mock_client.list_nics.return_value = [{"id": "n1", "name": "n"}]
    mock_client.delete_nic.return_value = {"id": "n1"}
    result = CliRunner().invoke(nic, ["delete", "n", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_nic.assert_called_once_with("n1")
