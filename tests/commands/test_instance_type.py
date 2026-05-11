from __future__ import annotations

import json

from click.testing import CliRunner

from app.commands.instance_type import instance_type


def test_instance_type_list_with_activated_filter(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [
        {
            "id": "it1",
            "name": "M-8",
            "cpu_vcore": 8,
            "memory_gib": 32,
            "devices": [],
            "activated": True,
        }
    ]
    result = CliRunner().invoke(
        instance_type, ["list", "--activated", "true", "--format", "json"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    mock_client.list_instance_types.assert_called_once()
    assert mock_client.list_instance_types.call_args.kwargs["activated"] is True


def test_instance_type_json_keeps_raw_devices_list(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [
        {
            "id": "it-g",
            "name": "G-NHHS-160",
            "cpu_vcore": 48,
            "memory_gib": 480,
            "devices": ["nvidia_h100_80gb_sxm", "nvidia_h100_80gb_sxm"],
            "activated": True,
        }
    ]
    result = CliRunner().invoke(
        instance_type, ["list", "--format", "json"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data[0]["devices"] == [
        "nvidia_h100_80gb_sxm",
        "nvidia_h100_80gb_sxm",
    ]


def test_instance_type_table_summarizes_devices(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [
        {
            "id": "it-cpu",
            "name": "C-2",
            "cpu_vcore": 2,
            "memory_gib": 4,
            "devices": [],
            "activated": True,
        },
        {
            "id": "it-gpu",
            "name": "G-NHHS-160",
            "cpu_vcore": 48,
            "memory_gib": 480,
            "devices": ["nvidia_h100_80gb_sxm", "nvidia_h100_80gb_sxm"],
            "activated": True,
        },
    ]
    result = CliRunner().invoke(instance_type, ["list", "--format", "csv"], obj=app_obj)
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert lines[0] == "name,cpu_vcore,memory_gib,accelerators"
    assert lines[1] == "C-2,2,4,cpu only"
    assert lines[2] == "G-NHHS-160,48,480,2x nvidia_h100_80gb_sxm"
