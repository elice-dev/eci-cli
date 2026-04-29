from __future__ import annotations

import yaml
from click.testing import CliRunner

from app.commands.compute.launch import vm_launch


def _vm_pricing(mock_client):
    mock_client.list_pricings.return_value = [{"id": "p-vm", "name": "M-8"}]
    mock_client.get_pricing.return_value = {
        "id": "p-vm",
        "name": "M-8",
        "resource_kind": "vm_allocation",
        "resource_id": "it-uuid",
    }


def _stub_full_launch(mock_client):
    _vm_pricing(mock_client)
    mock_client.list_images.return_value = [{"id": "img-uuid", "name": "ubuntu"}]
    mock_client.list_subnets.return_value = [{"id": "sn-uuid", "name": "default"}]
    mock_client.find_pricing.side_effect = lambda name, **_: {
        "id": f"p-{name}",
        "name": name,
    }
    mock_client.create_vm.return_value = {"id": "vm-1", "name": "demo"}
    mock_client.create_block_storage.return_value = {"id": "bs-1"}
    mock_client.create_nic.return_value = {"id": "nic-1"}
    mock_client.create_public_ip.return_value = {"id": "ip-1"}
    mock_client.attach_block_storage.return_value = {"ok": True}
    mock_client.attach_nic.return_value = {"ok": True}
    mock_client.attach_public_ip.return_value = {"ok": True}
    mock_client.create_allocation.return_value = {"id": "alloc-1"}
    mock_client.wait_for_status.return_value = {"status": "prepared"}


def test_launch_full_path(mock_client, app_obj, isolated_config_path):
    _stub_full_launch(mock_client)

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
            "--subnet",
            "default",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    mock_client.create_vm.assert_called_once()
    mock_client.create_block_storage.assert_called_once()
    mock_client.create_nic.assert_called_once()
    mock_client.create_public_ip.assert_called_once()
    mock_client.create_allocation.assert_called_once_with("vm-1")


def test_launch_no_network_skips_nic_and_ip(mock_client, app_obj, isolated_config_path):
    _stub_full_launch(mock_client)

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
            "--no-network",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    mock_client.create_nic.assert_not_called()
    mock_client.create_public_ip.assert_not_called()


def test_launch_no_public_ip_creates_nic_only(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
            "--subnet",
            "default",
            "--no-public-ip",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    mock_client.create_nic.assert_called_once()
    mock_client.create_public_ip.assert_not_called()


def test_launch_no_start_skips_allocation(mock_client, app_obj, isolated_config_path):
    _stub_full_launch(mock_client)

    CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
            "--subnet",
            "default",
            "--no-start",
        ],
        obj=app_obj,
    )
    mock_client.create_allocation.assert_not_called()


def test_launch_reuses_existing_block_storage(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.list_block_storages.return_value = [
        {"id": "bs-existing", "name": "data"}
    ]

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--subnet",
            "default",
            "--block-storage",
            "data",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    mock_client.create_block_storage.assert_not_called()
    mock_client.attach_block_storage.assert_called_once_with("bs-existing", "vm-1")


def test_launch_block_storage_conflicts_with_size(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.list_block_storages.return_value = [{"id": "bs-1", "name": "data"}]

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--subnet",
            "default",
            "--block-storage",
            "data",
            "--size-gib",
            "100",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "conflicts" in result.output


def test_launch_nic_conflicts_with_subnet(mock_client, app_obj, isolated_config_path):
    _stub_full_launch(mock_client)
    mock_client.list_nics.return_value = [{"id": "nic-1", "name": "n1"}]

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
            "--subnet",
            "default",
            "--nic",
            "n1",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "conflicts" in result.output


def test_launch_missing_pricing_errors(mock_client, app_obj, isolated_config_path):
    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--image",
            "u",
            "--size-gib",
            "100",
            "--subnet",
            "s",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "--pricing is required" in result.output


def test_launch_missing_subnet_errors(mock_client, app_obj, isolated_config_path):
    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "M-8",
            "--image",
            "u",
            "--size-gib",
            "100",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "--subnet is required" in result.output


def test_launch_rejects_non_vm_pricing(mock_client, app_obj, isolated_config_path):
    mock_client.list_pricings.return_value = [{"id": "p1", "name": "block"}]
    mock_client.get_pricing.return_value = {
        "id": "p1",
        "resource_kind": "block_storage",
        "resource_id": "x",
    }

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--pricing",
            "block",
            "--image",
            "u",
            "--size-gib",
            "100",
            "--subnet",
            "s",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "is not a VM pricing" in result.output


def test_launch_uses_defined_spec(mock_client, app_obj, isolated_config_path):
    _, path = isolated_config_path
    path.write_text(
        yaml.safe_dump(
            {
                "vm_defaults": {
                    "default": {
                        "username": "ubuntu",
                        "pricing": "M-8",
                        "image": "ubuntu",
                        "size_gib": 50,
                        "subnet": "default",
                    }
                }
            }
        )
    )
    _stub_full_launch(mock_client)

    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo", "--password", "pw", "--defined", "default"],
        obj=app_obj,
        input="n\n",
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_vm.call_args.kwargs
    assert kwargs["username"] == "ubuntu"
    assert mock_client.create_block_storage.call_args.kwargs["size_gib"] == 50


def test_launch_unknown_defined_spec_errors(mock_client, app_obj, isolated_config_path):
    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo", "--password", "pw", "--defined", "missing"],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "no vm_defaults spec" in result.output
