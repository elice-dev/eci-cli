from __future__ import annotations

from click.testing import CliRunner

from app.commands.storage.pfs import pfs


def test_pfs_create(mock_client, app_obj):
    mock_client.create_pfs.return_value = {"id": "pf1"}
    result = CliRunner().invoke(
        pfs, ["create", "--name", "p", "--size-gib", "1000"], obj=app_obj
    )
    assert result.exit_code == 0
    assert mock_client.create_pfs.call_args.kwargs == {"name": "p", "size_gib": 1000}


def test_pfs_update_no_fields(mock_client, app_obj):
    mock_client.list_pfs.return_value = [{"id": "pf1", "name": "p"}]
    result = CliRunner().invoke(pfs, ["update", "p"], obj=app_obj)
    assert result.exit_code != 0


def test_pfs_update_partial(mock_client, app_obj):
    mock_client.list_pfs.return_value = [{"id": "pf1", "name": "p"}]
    mock_client.update_pfs.return_value = {"id": "pf1"}
    result = CliRunner().invoke(
        pfs, ["update", "p", "--name", "new"], obj=app_obj
    )
    assert result.exit_code == 0
    assert mock_client.update_pfs.call_args.kwargs == {"name": "new"}


def test_pfs_delete(mock_client, app_obj):
    mock_client.list_pfs.return_value = [{"id": "pf1", "name": "p"}]
    mock_client.delete_pfs.return_value = {"id": "pf1"}
    result = CliRunner().invoke(pfs, ["delete", "p", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_pfs.assert_called_once_with("pf1")


def test_pfs_member_create(mock_client, app_obj):
    mock_client.list_pfs.return_value = [{"id": "pf1", "name": "p"}]
    mock_client.list_vms.return_value = [{"id": "vm1", "name": "vm"}]
    mock_client.create_pfs_member.return_value = {"id": "m1"}

    result = CliRunner().invoke(
        pfs, ["member", "create", "--pfs", "p", "--vm", "vm"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_pfs_member.call_args.kwargs
    assert kwargs == {"pfs_id": "pf1", "machine_id": "vm1"}


def test_pfs_member_delete_uses_raw_id(mock_client, app_obj):
    mock_client.delete_pfs_member.return_value = {"id": "m1"}
    result = CliRunner().invoke(
        pfs, ["member", "delete", "m-uuid", "-y"], obj=app_obj
    )
    assert result.exit_code == 0
    mock_client.delete_pfs_member.assert_called_once_with("m-uuid")
