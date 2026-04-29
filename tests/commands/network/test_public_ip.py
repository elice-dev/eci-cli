from __future__ import annotations

from click.testing import CliRunner

from app.commands.network.public_ip import public_ip as ip


def test_ip_create(mock_client, app_obj):
    mock_client.list_pricings.return_value = [{"id": "p-uuid", "name": "Public IP"}]
    mock_client.create_public_ip.return_value = {"id": "ip-1"}

    result = CliRunner().invoke(
        ip, ["create", "--pricing", "Public IP", "--no-ddos"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_public_ip.call_args.kwargs
    assert kwargs["pricing_id"] == "p-uuid"
    assert kwargs["ddos"] is False


def test_ip_update_parses_tags(mock_client, app_obj):
    mock_client.list_public_ips.return_value = [{"id": "ip-1", "ip": "1.2.3.4"}]
    mock_client.update_public_ip.return_value = {"id": "ip-1"}

    result = CliRunner().invoke(
        ip,
        ["update", "1.2.3.4", "--tag", "env=prod", "--tag", "owner=team"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.update_public_ip.call_args.kwargs
    assert kwargs["tags"] == {"env": "prod", "owner": "team"}


def test_ip_update_invalid_tag_format(mock_client, app_obj):
    mock_client.list_public_ips.return_value = [{"id": "ip-1", "ip": "1.2.3.4"}]
    result = CliRunner().invoke(ip, ["update", "1.2.3.4", "--tag", "bad"], obj=app_obj)
    assert result.exit_code != 0
    assert "invalid --tag" in result.output


def test_ip_update_no_tags_errors(mock_client, app_obj):
    mock_client.list_public_ips.return_value = [{"id": "ip-1", "ip": "1.2.3.4"}]
    result = CliRunner().invoke(ip, ["update", "1.2.3.4"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_ip_attach(mock_client, app_obj):
    mock_client.list_public_ips.return_value = [{"id": "ip-1", "ip": "1.2.3.4"}]
    mock_client.list_nics.return_value = [{"id": "nic-1", "name": "n"}]
    mock_client.attach_public_ip.return_value = {"ok": True}

    result = CliRunner().invoke(ip, ["attach", "1.2.3.4", "--nic", "n"], obj=app_obj)
    assert result.exit_code == 0, result.output
    mock_client.attach_public_ip.assert_called_once_with("ip-1", "nic-1")


def test_ip_detach(mock_client, app_obj):
    mock_client.list_public_ips.return_value = [{"id": "ip-1", "ip": "1.2.3.4"}]
    mock_client.attach_public_ip.return_value = {"ok": True}

    result = CliRunner().invoke(ip, ["detach", "1.2.3.4"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.attach_public_ip.assert_called_once_with("ip-1", None)


def test_ip_delete(mock_client, app_obj):
    mock_client.list_public_ips.return_value = [{"id": "ip-1", "ip": "1.2.3.4"}]
    mock_client.delete_public_ip.return_value = {"id": "ip-1"}
    result = CliRunner().invoke(ip, ["delete", "1.2.3.4", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_public_ip.assert_called_once_with("ip-1")
