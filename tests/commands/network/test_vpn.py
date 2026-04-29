from __future__ import annotations

from click.testing import CliRunner

from app.commands.network.vpn import vpn


def test_vpn_create(mock_client, app_obj):
    mock_client.list_subnets.return_value = [{"id": "s1", "name": "s"}]
    mock_client.create_vpn.return_value = {"id": "vpn-1"}

    result = CliRunner().invoke(vpn, ["create", "--subnet", "s"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert mock_client.create_vpn.call_args.kwargs["attached_subnet_id"] == "s1"


def test_vpn_delete_with_resolution(mock_client, app_obj):
    mock_client.list_vpns.return_value = [{"id": "vpn-uuid", "name": "vpn1"}]
    mock_client.delete_vpn.return_value = {"id": "vpn-uuid"}
    result = CliRunner().invoke(vpn, ["delete", "vpn1", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_vpn.assert_called_once_with("vpn-uuid")


def test_vpn_delete_falls_back_to_raw_id_when_resolve_fails(mock_client, app_obj):
    mock_client.list_vpns.return_value = []
    mock_client.delete_vpn.return_value = {"id": "raw-id"}

    result = CliRunner().invoke(vpn, ["delete", "raw-id", "-y"], obj=app_obj)
    assert result.exit_code == 0, result.output
    mock_client.delete_vpn.assert_called_once_with("raw-id")
