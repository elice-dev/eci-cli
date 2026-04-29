from __future__ import annotations

from click.testing import CliRunner

from app.commands.instance_type import instance_type


def test_instance_type_list_with_activated_filter(mock_client, app_obj):
    mock_client.list_instance_types.return_value = [
        {"id": "it1", "name": "M-8", "cpu_vcore": 8, "memory_gib": 32, "activated": True}
    ]
    result = CliRunner().invoke(
        instance_type, ["--activated", "true", "--format", "json"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    mock_client.list_instance_types.assert_called_once()
    assert mock_client.list_instance_types.call_args.kwargs["activated"] is True
