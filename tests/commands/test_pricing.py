from __future__ import annotations

import json

from click.testing import CliRunner

from app.commands.pricing import pricing


def test_pricing_list(mock_client, app_obj):
    mock_client.list_pricings.return_value = [
        {
            "id": "p1",
            "name": "M-8",
            "resource_kind": "vm_allocation",
            "resource_id": "it-uuid",
            "pricing_type": "ondemand",
            "price_per_hour": 100,
            "activated": True,
        }
    ]
    mock_client.list_instance_types.return_value = [{"id": "it-uuid", "name": "M-8"}]
    result = CliRunner().invoke(pricing, ["--format", "json"], obj=app_obj)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data[0]["name"] == "M-8"


def test_pricing_hides_pricings_for_deactivated_instance_types(mock_client, app_obj):
    mock_client.list_pricings.return_value = [
        {
            "id": "p1",
            "name": "M-8",
            "resource_kind": "vm_allocation",
            "resource_id": "active-it",
            "pricing_type": "ondemand",
            "price_per_hour": 100,
            "activated": True,
        },
        {
            "id": "p2",
            "name": "removed",
            "resource_kind": "vm_allocation",
            "resource_id": "stale-it",
            "pricing_type": "ondemand",
            "price_per_hour": 1,
            "activated": True,
        },
    ]
    mock_client.list_instance_types.return_value = [{"id": "active-it", "name": "M-8"}]
    result = CliRunner().invoke(pricing, ["--format", "json"], obj=app_obj)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [p["id"] for p in data] == ["p1"]


def test_pricing_filter_resource_ids_resolved(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [
        {"id": "it-uuid", "name": "M-8"},
        {"id": "it-uuid2", "name": "M-16"},
    ]
    mock_client.list_pricings.return_value = []
    result = CliRunner().invoke(pricing, ["--resource-ids", "M-8,M-16"], obj=app_obj)
    assert result.exit_code == 0, result.output
    kwargs = mock_client.list_pricings.call_args.kwargs
    assert kwargs["resource_ids"] == ["it-uuid", "it-uuid2"]
