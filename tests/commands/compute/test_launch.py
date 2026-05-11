from __future__ import annotations

import yaml
from click.testing import CliRunner

from app.commands.compute.launch import vm_launch


def _stub_full_launch(mock_client):
    mock_client.list_instance_types.return_value = [{"id": "it-uuid", "name": "M-8"}]
    mock_client.list_pricings.return_value = [
        {"id": "p-vm", "resource_id": "it-uuid", "pricing_type": "ondemand"}
    ]
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
            "--instance-type",
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
            "--instance-type",
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
            "--instance-type",
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
            "--instance-type",
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
            "--instance-type",
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
            "--instance-type",
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
            "--instance-type",
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


def test_launch_prompts_for_missing_fields_with_defaults(
    mock_client, app_obj, isolated_config_path, monkeypatch
):
    monkeypatch.setattr("app.commands.compute.launch._is_tty", lambda: True)
    _stub_full_launch(mock_client)
    mock_client.list_instance_types.return_value = [
        {"id": "it-uuid", "name": "C-2", "devices": []}
    ]
    mock_client.list_images.return_value = [
        {"id": "img-uuid", "name": "Ubuntu 24.04 LTS (Standard)"}
    ]
    mock_client.list_subnets.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "eci-default-subnet"}
    ]

    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo", "--password", "pw"],
        input="\n\n\n",
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    assert "instance type [C-2]" in result.output
    assert "image [Ubuntu 24.04 LTS (Standard)]" in result.output
    assert "root disk size (GiB) [20]" in result.output


def test_launch_silently_uses_defaults_in_non_tty(
    mock_client, app_obj, isolated_config_path
):
    """Non-interactive callers (AI / scripts / CI) get defaults silently."""
    _stub_full_launch(mock_client)
    mock_client.list_instance_types.return_value = [
        {"id": "it-uuid", "name": "C-2", "devices": []}
    ]
    mock_client.list_images.return_value = [
        {"id": "img-uuid", "name": "Ubuntu 24.04 LTS (Standard)"}
    ]
    mock_client.list_subnets.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "eci-default-subnet"}
    ]

    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo", "--password", "pw"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    assert "instance type [" not in result.output
    assert "image [" not in result.output
    mock_client.create_vm.assert_called_once()


def test_launch_errors_in_non_tty_when_password_missing(
    mock_client, app_obj, isolated_config_path
):
    """Password has no safe default; non-TTY should error, not abort."""
    _stub_full_launch(mock_client)
    mock_client.list_instance_types.return_value = [
        {"id": "it-uuid", "name": "C-2", "devices": []}
    ]
    mock_client.list_images.return_value = [
        {"id": "img-uuid", "name": "Ubuntu 24.04 LTS (Standard)"}
    ]
    mock_client.list_subnets.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "eci-default-subnet"}
    ]

    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo"],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "--password is required" in result.output


def test_launch_prompts_pick_gpu_defaults_for_accelerator_instance(
    mock_client, app_obj, isolated_config_path, monkeypatch
):
    monkeypatch.setattr("app.commands.compute.launch._is_tty", lambda: True)
    _stub_full_launch(mock_client)
    mock_client.list_instance_types.return_value = [
        {
            "id": "it-gpu",
            "name": "G-NHHS-80",
            "devices": ["nvidia_h100_80gb_sxm"],
        }
    ]
    mock_client.list_images.return_value = [
        {"id": "img-gpu", "name": "Ubuntu 24.04 LTS (AI/GPU)"}
    ]
    mock_client.list_subnets.return_value = [
        {"id": "22222222-2222-2222-2222-222222222222", "name": "eci-default-subnet"}
    ]

    result = CliRunner().invoke(
        vm_launch,
        ["--name", "ml-1", "--instance-type", "G-NHHS-80", "--password", "pw"],
        input="\n\n",
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    assert "image [Ubuntu 24.04 LTS (AI/GPU)]" in result.output
    assert "root disk size (GiB) [50]" in result.output


def test_launch_without_subnet_reuses_existing_default(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    default_subnet_uuid = "33333333-3333-3333-3333-333333333333"
    mock_client.list_subnets.return_value = [
        {"id": default_subnet_uuid, "name": "eci-default-subnet"}
    ]

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    mock_client.create_vnet.assert_not_called()
    mock_client.create_subnet.assert_not_called()
    nic_call = mock_client.create_nic.call_args.kwargs
    assert nic_call["attached_subnet_id"] == default_subnet_uuid


def test_launch_without_subnet_creates_default_vnet_and_subnet(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.list_subnets.return_value = []  # default doesn't exist
    mock_client.list_vnets.return_value = []  # default vnet doesn't exist either
    new_vnet_uuid = "44444444-4444-4444-4444-444444444444"
    new_subnet_uuid = "55555555-5555-5555-5555-555555555555"
    mock_client.create_vnet.return_value = {"id": new_vnet_uuid}
    mock_client.create_subnet.return_value = {"id": new_subnet_uuid}

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
            "M-8",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
        ],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    vnet_kwargs = mock_client.create_vnet.call_args.kwargs
    assert vnet_kwargs["name"] == "eci-default-vnet"
    subnet_kwargs = mock_client.create_subnet.call_args.kwargs
    assert subnet_kwargs["name"] == "eci-default-subnet"
    assert subnet_kwargs["attached_network_id"] == new_vnet_uuid


def test_launch_rejects_non_vm_pricing_id(mock_client, app_obj, isolated_config_path):
    mock_client.get_pricing.return_value = {
        "id": "22222222-2222-2222-2222-222222222222",
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
            "--pricing-id",
            "22222222-2222-2222-2222-222222222222",
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
    assert "not a VM pricing" in result.output


def test_launch_uses_defined_spec(mock_client, app_obj, isolated_config_path):
    _, path = isolated_config_path
    path.write_text(
        yaml.safe_dump(
            {
                "vm_defaults": {
                    "default": {
                        "username": "ubuntu",
                        "instance_type": "M-8",
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
        ["--name", "demo", "--password", "pw", "--spec", "default"],
        obj=app_obj,
    )
    assert result.exit_code == 0, result.output
    kwargs = mock_client.create_vm.call_args.kwargs
    assert kwargs["username"] == "ubuntu"
    assert mock_client.create_block_storage.call_args.kwargs["size_gib"] == 50


def test_launch_unknown_spec_errors(mock_client, app_obj, isolated_config_path):
    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo", "--password", "pw", "--spec", "missing"],
        obj=app_obj,
    )
    assert result.exit_code != 0
    assert "no vm-spec" in result.output


_FULL_SPEC = {
    "username": "ubuntu",
    "instance_type": "M-8",
    "image": "ubuntu",
    "size_gib": 50,
    "subnet": "default",
}


def _write_vm_defaults(path, specs: dict) -> None:
    path.write_text(yaml.safe_dump({"vm_defaults": specs}))


def test_launch_spec_no_override_does_not_prompt_to_save(
    mock_client, app_obj, isolated_config_path
):
    _, path = isolated_config_path
    _write_vm_defaults(path, {"default": _FULL_SPEC})
    _stub_full_launch(mock_client)

    result = CliRunner().invoke(
        vm_launch,
        ["--name", "demo", "--password", "pw", "--spec", "default"],
        obj=app_obj,
        input="",
    )
    assert result.exit_code == 0, result.output
    assert "Save these arguments" not in result.output


def test_launch_spec_with_override_prompts_to_save(
    mock_client, app_obj, isolated_config_path, monkeypatch
):
    monkeypatch.setattr("app.commands.compute.launch._is_tty", lambda: True)
    _, path = isolated_config_path
    _write_vm_defaults(path, {"default": _FULL_SPEC})
    _stub_full_launch(mock_client)

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--spec",
            "default",
            "--size-gib",
            "200",
        ],
        obj=app_obj,
        input="n\n",
    )
    assert result.exit_code == 0, result.output
    assert "Save these arguments" in result.output


def test_launch_rolls_back_when_nic_creation_fails(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.create_nic.side_effect = RuntimeError("subnet unreachable")

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
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
    assert result.exit_code != 0
    mock_client.attach_block_storage.assert_any_call("bs-1", None)
    mock_client.delete_block_storage.assert_called_once_with("bs-1")
    mock_client.delete_vm.assert_called_once_with("vm-1")
    mock_client.delete_nic.assert_not_called()


def test_launch_rolls_back_after_allocation_failure(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.create_allocation.side_effect = RuntimeError("out of capacity")

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
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
    assert result.exit_code != 0
    mock_client.attach_public_ip.assert_any_call("ip-1", None)
    mock_client.delete_public_ip.assert_called_once_with("ip-1")
    mock_client.attach_nic.assert_any_call("nic-1", None)
    mock_client.delete_nic.assert_called_once_with("nic-1")
    mock_client.attach_block_storage.assert_any_call("bs-1", None)
    mock_client.delete_block_storage.assert_called_once_with("bs-1")
    mock_client.delete_vm.assert_called_once_with("vm-1")


def test_launch_rollback_does_not_delete_reused_block_storage(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.list_block_storages.return_value = [
        {"id": "bs-existing", "name": "data"}
    ]
    mock_client.create_nic.side_effect = RuntimeError("nope")

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
            "M-8",
            "--subnet",
            "default",
            "--block-storage",
            "data",
        ],
        obj=app_obj,
    )
    assert result.exit_code != 0
    mock_client.attach_block_storage.assert_any_call("bs-existing", None)
    mock_client.delete_block_storage.assert_not_called()
    mock_client.delete_vm.assert_called_once_with("vm-1")


def test_launch_warns_when_allocation_response_missing_id(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.create_allocation.return_value = "unexpected-non-dict-response"

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
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
    assert "did not include id" in result.output


def test_launch_rollback_continues_when_one_cleanup_fails(
    mock_client, app_obj, isolated_config_path
):
    _stub_full_launch(mock_client)
    mock_client.create_allocation.side_effect = RuntimeError("boom")
    mock_client.attach_public_ip.side_effect = [
        {"ok": True},
        RuntimeError("detach failed"),
    ]

    result = CliRunner().invoke(
        vm_launch,
        [
            "--name",
            "demo",
            "--password",
            "pw",
            "--instance-type",
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
    assert result.exit_code != 0
    mock_client.delete_nic.assert_called_once_with("nic-1")
    mock_client.delete_block_storage.assert_called_once_with("bs-1")
    mock_client.delete_vm.assert_called_once_with("vm-1")
