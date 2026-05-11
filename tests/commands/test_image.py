from __future__ import annotations

from click.testing import CliRunner

from app.commands.image import image


def test_image_list(mock_client, app_obj):
    mock_client.list_images.return_value = [
        {"id": "img1", "name": "ubuntu-22.04", "size_gib": 20, "status": "ready"}
    ]
    result = CliRunner().invoke(image, ["list", "--format", "csv"], obj=app_obj)
    assert result.exit_code == 0, result.output
    assert "ubuntu-22.04" in result.output
