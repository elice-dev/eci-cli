from __future__ import annotations

import json

from click.testing import CliRunner

from app.commands.org import org


def test_org_info_json(mock_client, app_obj):
    mock_client.organization.return_value = {"id": "o1", "name": "elice"}
    result = CliRunner().invoke(org, ["info", "--format", "json"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["name"] == "elice"
    mock_client.organization.assert_called_once()


def test_org_info_table(mock_client, app_obj):
    mock_client.organization.return_value = {"id": "o1", "name": "elice"}
    result = CliRunner().invoke(org, ["info"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert "elice" in result.output


def test_org_usage_json_uses_action_result(mock_client, app_obj):
    mock_client.organization_resource_usage.return_value = {"vm_count": 3}
    result = CliRunner().invoke(org, ["usage", "--format", "json"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"vm_count": 3}


def test_org_usage_table(mock_client, app_obj):
    mock_client.organization_resource_usage.return_value = {"vm_count": 3}
    result = CliRunner().invoke(org, ["usage"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert "vm_count" in result.output
