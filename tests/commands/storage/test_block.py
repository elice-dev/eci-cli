from __future__ import annotations

from click.testing import CliRunner

from app.commands.storage.block import block


def test_block_create_resolves_pricing_and_image(mock_client, app_obj):
    mock_client.list_pricings.return_value = [{"id": "p1", "name": "block-pricing"}]
    mock_client.list_images.return_value = [{"id": "img-uuid", "name": "ubuntu"}]
    mock_client.create_block_storage.return_value = {"id": "bs-1"}

    result = CliRunner().invoke(
        block,
        [
            "create",
            "--name",
            "data",
            "--size-gib",
            "100",
            "--pricing",
            "block-pricing",
            "--image",
            "ubuntu",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_block_storage.call_args.kwargs
    assert kwargs["name"] == "data"
    assert kwargs["size_gib"] == 100
    assert kwargs["pricing_id"] == "p1"
    assert kwargs["image_id"] == "img-uuid"
    assert kwargs["snapshot_id"] is None


def test_block_create_image_and_snapshot_mutually_exclusive(mock_client, app_obj):
    result = CliRunner().invoke(
        block,
        [
            "create",
            "--name",
            "d",
            "--size-gib",
            "10",
            "--pricing",
            "p",
            "--image",
            "i",
            "--snapshot",
            "s",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
    mock_client.create_block_storage.assert_not_called()


def test_block_update_no_fields(mock_client, app_obj):
    mock_client.list_block_storages.return_value = [{"id": "b1", "name": "d"}]
    result = CliRunner().invoke(block, ["update", "d"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_block_update_resizes(mock_client, app_obj):
    mock_client.list_block_storages.return_value = [{"id": "b1", "name": "d"}]
    mock_client.update_block_storage.return_value = {"id": "b1"}
    result = CliRunner().invoke(
        block, ["update", "d", "--size-gib", "200"], obj=app_obj
    )
    assert result.exit_code == 0, result.output
    assert mock_client.update_block_storage.call_args.kwargs["size_gib"] == 200


def test_block_attach_and_detach(mock_client, app_obj):
    mock_client.list_block_storages.return_value = [{"id": "b1", "name": "d"}]
    mock_client.list_vms.return_value = [{"id": "vm-1", "name": "vm"}]
    mock_client.attach_block_storage.return_value = {"ok": True}

    r1 = CliRunner().invoke(block, ["attach", "d", "--vm", "vm"], obj=app_obj)
    assert r1.exit_code == 0
    mock_client.attach_block_storage.assert_called_with("b1", "vm-1")

    r2 = CliRunner().invoke(block, ["detach", "d"], obj=app_obj)
    assert r2.exit_code == 0
    mock_client.attach_block_storage.assert_called_with("b1", None)


def test_block_delete(mock_client, app_obj):
    mock_client.list_block_storages.return_value = [{"id": "b1", "name": "d"}]
    mock_client.delete_block_storage.return_value = {"id": "b1"}
    result = CliRunner().invoke(block, ["delete", "d", "-y"], obj=app_obj)
    assert result.exit_code == 0
    mock_client.delete_block_storage.assert_called_once_with("b1")


def test_block_snapshot_create(mock_client, app_obj):
    mock_client.list_block_storages.return_value = [{"id": "b1", "name": "data"}]
    mock_client.create_block_snapshot.return_value = {"id": "snap-1"}

    result = CliRunner().invoke(
        block,
        ["snapshot", "create", "--name", "snap1", "--block", "data"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_block_snapshot.call_args.kwargs
    assert kwargs["name"] == "snap1"
    assert kwargs["block_storage_id"] == "b1"


def test_block_snapshot_update_renames(mock_client, app_obj):
    mock_client.list_block_snapshots.return_value = [{"id": "s1", "name": "old"}]
    mock_client.update_block_snapshot.return_value = {"id": "s1"}
    result = CliRunner().invoke(
        block, ["snapshot", "update", "old", "--name", "new"], obj=app_obj
    )
    assert result.exit_code == 0
    assert mock_client.update_block_snapshot.call_args.kwargs["name"] == "new"


def test_block_snapshot_delete(mock_client, app_obj):
    mock_client.list_block_snapshots.return_value = [{"id": "s1", "name": "snap1"}]
    mock_client.delete_block_snapshot.return_value = {"id": "s1"}
    result = CliRunner().invoke(
        block, ["snapshot", "delete", "snap1", "-y"], obj=app_obj
    )
    assert result.exit_code == 0
    mock_client.delete_block_snapshot.assert_called_once_with("s1")


def test_block_scheduler_create(mock_client, app_obj):
    mock_client.list_block_storages.return_value = [{"id": "b1", "name": "data"}]
    mock_client.create_snapshot_scheduler.return_value = {"id": "sched-1"}

    result = CliRunner().invoke(
        block,
        [
            "scheduler",
            "create",
            "--name",
            "daily",
            "--block",
            "data",
            "--cron",
            "0 0 * * *",
            "--max-snapshots",
            "7",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_snapshot_scheduler.call_args.kwargs
    assert kwargs == {
        "name": "daily",
        "block_storage_id": "b1",
        "cron_expression": "0 0 * * *",
        "max_snapshots": 7,
    }


def test_block_scheduler_update_no_fields_errors(mock_client, app_obj):
    mock_client.list_snapshot_schedulers.return_value = [{"id": "s1", "name": "daily"}]
    result = CliRunner().invoke(block, ["scheduler", "update", "daily"], obj=app_obj)
    assert result.exit_code != 0
    assert "nothing to update" in result.output


def test_block_scheduler_update_partial(mock_client, app_obj):
    mock_client.list_snapshot_schedulers.return_value = [{"id": "s1", "name": "daily"}]
    mock_client.update_snapshot_scheduler.return_value = {"id": "s1"}
    result = CliRunner().invoke(
        block,
        ["scheduler", "update", "daily", "--max-snapshots", "14"],
        obj=app_obj,
    )
    assert result.exit_code == 0
    kwargs = mock_client.update_snapshot_scheduler.call_args.kwargs
    assert kwargs == {"max_snapshots": 14}


def test_block_scheduler_delete(mock_client, app_obj):
    mock_client.list_snapshot_schedulers.return_value = [{"id": "s1", "name": "daily"}]
    mock_client.delete_snapshot_scheduler.return_value = {"id": "s1"}
    result = CliRunner().invoke(
        block, ["scheduler", "delete", "daily", "-y"], obj=app_obj
    )
    assert result.exit_code == 0
    mock_client.delete_snapshot_scheduler.assert_called_once_with("s1")
