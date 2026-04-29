from __future__ import annotations

from click.testing import CliRunner

from app.commands.storage.object import obj


def test_object_create(mock_client, app_obj):
    mock_client.create_object_storage.return_value = {"id": "o1"}
    result = CliRunner().invoke(
        obj, ["create", "--name", "bucket", "--size-gib", "500"], obj=app_obj
    )
    assert result.exit_code == 0
    kwargs = mock_client.create_object_storage.call_args.kwargs
    assert kwargs == {"name": "bucket", "size_gib": 500}


def test_object_update_no_fields_errors(mock_client, app_obj):
    mock_client.list_object_storages.return_value = [{"id": "o1", "name": "bucket"}]
    result = CliRunner().invoke(obj, ["update", "bucket"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_object_update_resizes(mock_client, app_obj):
    mock_client.list_object_storages.return_value = [{"id": "o1", "name": "bucket"}]
    mock_client.update_object_storage.return_value = {"id": "o1"}
    result = CliRunner().invoke(
        obj, ["update", "bucket", "--size-gib", "1000"], obj=app_obj
    )
    assert result.exit_code == 0
    assert mock_client.update_object_storage.call_args.kwargs["size_gib"] == 1000


def test_object_delete(mock_client, app_obj):
    mock_client.list_object_storages.return_value = [{"id": "o1", "name": "bucket"}]
    mock_client.delete_object_storage.return_value = {"id": "o1"}
    result = CliRunner().invoke(obj, ["delete", "bucket", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_object_storage.assert_called_once_with("o1")


def test_object_user_create_and_delete(mock_client, app_obj):
    mock_client.create_object_user.return_value = {"id": "u1"}
    mock_client.list_object_users.return_value = [{"id": "u1", "name": "alice"}]
    mock_client.delete_object_user.return_value = {"id": "u1"}

    r1 = CliRunner().invoke(obj, ["user", "create", "--name", "alice"], obj=app_obj)
    assert r1.exit_code == 0
    assert mock_client.create_object_user.call_args.kwargs == {"name": "alice"}

    r2 = CliRunner().invoke(obj, ["user", "delete", "alice", "-y"], obj=app_obj)
    assert r2.exit_code == 0
    mock_client.delete_object_user.assert_called_once_with("u1")


def test_object_user_update_no_fields(mock_client, app_obj):
    mock_client.list_object_users.return_value = [{"id": "u1", "name": "alice"}]
    result = CliRunner().invoke(obj, ["user", "update", "alice"], obj=app_obj)
    assert result.exit_code != 0


def test_object_grant_create(mock_client, app_obj):
    mock_client.list_object_storages.return_value = [{"id": "o1", "name": "bucket"}]
    mock_client.list_object_users.return_value = [{"id": "u1", "name": "alice"}]
    mock_client.create_object_grant.return_value = {"id": "g1"}

    result = CliRunner().invoke(
        obj,
        [
            "user",
            "grant",
            "create",
            "--bucket",
            "bucket",
            "--user",
            "alice",
            "--permission",
            "read_write",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_object_grant.call_args.kwargs
    assert kwargs == {
        "object_storage_id": "o1",
        "object_storage_user_id": "u1",
        "permission": "read_write",
    }


def test_object_grant_create_invalid_permission(mock_client, app_obj):
    result = CliRunner().invoke(
        obj,
        [
            "user",
            "grant",
            "create",
            "--bucket",
            "b",
            "--user",
            "u",
            "--permission",
            "admin",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0


def test_object_grant_update_passes_grant_id_directly(mock_client, app_obj):
    mock_client.update_object_grant.return_value = {"id": "g1"}
    result = CliRunner().invoke(
        obj,
        ["user", "grant", "update", "g1", "--permission", "read_only"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    args = mock_client.update_object_grant.call_args
    assert args.args[0] == "g1"
    assert args.kwargs["permission"] == "read_only"


def test_object_grant_delete(mock_client, app_obj):
    mock_client.delete_object_grant.return_value = {"id": "g1"}
    result = CliRunner().invoke(
        obj, ["user", "grant", "delete", "g1", "-y"], obj=app_obj
    )
    assert result.exit_code == 0
    mock_client.delete_object_grant.assert_called_once_with("g1")
