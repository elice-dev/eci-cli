from __future__ import annotations

import json

from click.testing import CliRunner

from app.commands.network.vnet import vnet


def test_vnet_create(mock_client, app_obj):
    mock_client.create_vnet.return_value = {"id": "v1"}
    result = CliRunner().invoke(
        vnet, ["create", "--name", "v", "--cidr", "10.0.0.0/16"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_vnet.call_args.kwargs
    assert kwargs == {"name": "v", "network_cidr": "10.0.0.0/16"}


def test_vnet_update_with_firewall_rules_json(mock_client, app_obj):
    mock_client.list_vnets.return_value = [{"id": "v1", "name": "v"}]
    mock_client.update_vnet.return_value = {"id": "v1"}
    rules = [{"port": 22}]
    result = CliRunner().invoke(
        vnet,
        ["update", "v", "--firewall-rules", json.dumps(rules)],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    args = mock_client.update_vnet.call_args
    assert args.args[0] == "v1"
    assert args.kwargs["firewall_rules"] == rules


def test_vnet_update_no_fields_errors(mock_client, app_obj):
    mock_client.list_vnets.return_value = [{"id": "v1", "name": "v"}]
    result = CliRunner().invoke(vnet, ["update", "v"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_vnet_delete_with_yes(mock_client, app_obj):
    mock_client.list_vnets.return_value = [{"id": "v1", "name": "v"}]
    mock_client.delete_vnet.return_value = {"id": "v1"}
    result = CliRunner().invoke(vnet, ["delete", "v", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_vnet.assert_called_once_with("v1")
