from __future__ import annotations

import json

from click.testing import CliRunner

from app.commands.region import region


def test_region_list(mock_client, app_obj):
    mock_client.list_regions.return_value = [{"id": "r1", "name": "kr"}]
    result = CliRunner().invoke(region, ["--format", "json"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)[0]["name"] == "kr"


def test_region_get_by_name(mock_client, app_obj):
    mock_client.list_regions.return_value = [{"id": "r1", "name": "kr"}]
    mock_client.get_region.return_value = {"id": "r1", "name": "kr"}
    result = CliRunner().invoke(region, ["kr", "--format", "json"], obj=app_obj)
    assert result.exit_code == 0, result.output
    mock_client.get_region.assert_called_once_with("r1")
