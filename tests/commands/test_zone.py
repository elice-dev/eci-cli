from __future__ import annotations

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from app.commands.zone import zone
from app.utils.name_resolver import AppContext


def _app(client: MagicMock) -> AppContext:
    return AppContext(client=client)


def test_zone_list_default_table_format():
    client = MagicMock()
    client.list_zones.return_value = [
        {"id": "z1", "name": "kr-central", "region_id": "r1"},
        {"id": "z2", "name": "kr-north", "region_id": "r1"},
    ]
    client.list_regions.return_value = [{"id": "r1", "name": "kr"}]

    runner = CliRunner()
    result = runner.invoke(zone, ["list"], obj=_app(client))
    assert result.exit_code == 0, result.output
    assert "kr-central" in result.output
    assert "kr-north" in result.output
    client.list_zones.assert_called_once()


def test_zone_list_json_format_resolves_region():
    client = MagicMock()
    client.list_zones.return_value = [
        {"id": "z1", "name": "kr-central", "region_id": "r1"}
    ]
    client.list_regions.return_value = [{"id": "r1", "name": "kr"}]

    runner = CliRunner()
    result = runner.invoke(zone, ["list", "--format", "json"], obj=_app(client))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data[0]["region"] == "kr"
    assert data[0]["name"] == "kr-central"


def test_zone_list_passes_filter_after_resolving_region_name():
    client = MagicMock()
    client.list_regions.return_value = [{"id": "r-uuid", "name": "kr"}]
    client.list_zones.return_value = []

    runner = CliRunner()
    result = runner.invoke(zone, ["list", "--region", "kr"], obj=_app(client))
    assert result.exit_code == 0, result.output
    client.list_zones.assert_called_once()
    assert client.list_zones.call_args.kwargs["region_id"] == "r-uuid"


def test_zone_get_via_positional_argument():
    client = MagicMock()
    client.list_zones.return_value = [{"id": "z-uuid", "name": "kr-central"}]
    client.get_zone.return_value = {
        "id": "z-uuid",
        "name": "kr-central",
        "region_id": "r1",
    }
    client.list_regions.return_value = [{"id": "r1", "name": "kr"}]

    runner = CliRunner()
    result = runner.invoke(zone, ["kr-central", "--format", "json"], obj=_app(client))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["name"] == "kr-central"
    client.get_zone.assert_called_once_with("z-uuid")


def test_zone_get_unknown_name_raises_user_error():
    client = MagicMock()
    client.list_zones.return_value = [{"id": "z-uuid", "name": "kr-central"}]

    runner = CliRunner()
    result = runner.invoke(zone, ["nonexistent"], obj=_app(client))
    assert result.exit_code != 0
    assert "no item named" in result.output
