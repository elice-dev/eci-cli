from __future__ import annotations

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from app.commands.compute.vm import vm
from app.utils.name_resolver import AppContext


def _app(client: MagicMock) -> AppContext:
    return AppContext(client=client)


_IT_UUID = "11111111-1111-1111-1111-111111111111"
_PRICING_UUID = "22222222-2222-2222-2222-222222222222"


def _create_args(*extra: str) -> list[str]:
    return [
        "create",
        "--name",
        "demo",
        "--username",
        "ubuntu",
        "--password",
        "pw",
        *extra,
    ]


def test_vm_create_with_instance_type_finds_ondemand_pricing():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.list_pricings.return_value = [
        {"id": _PRICING_UUID, "resource_id": _IT_UUID, "pricing_type": "ondemand"}
    ]
    client.create_vm.return_value = {"id": "vm-1"}

    result = CliRunner().invoke(
        vm, _create_args("--instance-type", "M-8"), obj=_app(client)
    )
    assert result.exit_code == 0, result.output
    kwargs = client.create_vm.call_args.kwargs
    assert kwargs["instance_type_id"] == _IT_UUID
    assert kwargs["pricing_id"] == _PRICING_UUID
    pricings_call = client.list_pricings.call_args.kwargs
    assert pricings_call.get("pricing_type") == "ondemand"
    assert pricings_call.get("resource_ids") == [_IT_UUID]


def test_vm_create_with_explicit_price_type():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.list_pricings.return_value = [
        {"id": _PRICING_UUID, "resource_id": _IT_UUID, "pricing_type": "spot"}
    ]
    client.create_vm.return_value = {"id": "vm-1"}

    result = CliRunner().invoke(
        vm,
        _create_args("--instance-type", "M-8", "--price-type", "spot"),
        obj=_app(client),
    )
    assert result.exit_code == 0, result.output
    assert client.list_pricings.call_args.kwargs.get("pricing_type") == "spot"


def test_vm_create_with_pricing_id_only():
    client = MagicMock()
    client.get_pricing.return_value = {
        "id": _PRICING_UUID,
        "resource_kind": "vm_allocation",
        "resource_id": _IT_UUID,
        "pricing_type": "reserved",
    }
    client.create_vm.return_value = {"id": "vm-1"}

    result = CliRunner().invoke(
        vm, _create_args("--pricing-id", _PRICING_UUID), obj=_app(client)
    )
    assert result.exit_code == 0, result.output
    kwargs = client.create_vm.call_args.kwargs
    assert kwargs["pricing_id"] == _PRICING_UUID
    assert kwargs["instance_type_id"] == _IT_UUID
    client.list_pricings.assert_not_called()


def test_vm_create_pricing_id_with_matching_instance_type_and_price_type():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.get_pricing.return_value = {
        "id": _PRICING_UUID,
        "resource_kind": "vm_allocation",
        "resource_id": _IT_UUID,
        "pricing_type": "spot",
    }
    client.create_vm.return_value = {"id": "vm-1"}

    result = CliRunner().invoke(
        vm,
        _create_args(
            "--instance-type",
            "M-8",
            "--price-type",
            "spot",
            "--pricing-id",
            _PRICING_UUID,
        ),
        obj=_app(client),
    )
    assert result.exit_code == 0, result.output


def test_vm_create_pricing_id_mismatched_instance_type_errors():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.get_pricing.return_value = {
        "id": _PRICING_UUID,
        "resource_kind": "vm_allocation",
        "resource_id": "different-it-uuid",
        "pricing_type": "ondemand",
    }

    result = CliRunner().invoke(
        vm,
        _create_args("--instance-type", "M-8", "--pricing-id", _PRICING_UUID),
        obj=_app(client),
    )
    assert result.exit_code != 0
    assert "instance-type mismatch" in result.output
    client.create_vm.assert_not_called()


def test_vm_create_pricing_id_mismatched_price_type_errors():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.get_pricing.return_value = {
        "id": _PRICING_UUID,
        "resource_kind": "vm_allocation",
        "resource_id": _IT_UUID,
        "pricing_type": "reserved",
    }

    result = CliRunner().invoke(
        vm,
        _create_args(
            "--instance-type",
            "M-8",
            "--price-type",
            "spot",
            "--pricing-id",
            _PRICING_UUID,
        ),
        obj=_app(client),
    )
    assert result.exit_code != 0
    assert "price-type mismatch" in result.output
    client.create_vm.assert_not_called()


def test_vm_create_pricing_id_must_be_uuid():
    client = MagicMock()
    result = CliRunner().invoke(
        vm, _create_args("--pricing-id", "not-a-uuid"), obj=_app(client)
    )
    assert result.exit_code != 0
    assert "must be a UUID" in result.output


def test_vm_create_rejects_non_vm_pricing_id():
    client = MagicMock()
    client.get_pricing.return_value = {
        "id": _PRICING_UUID,
        "resource_kind": "block_storage",
        "resource_id": "x",
    }

    result = CliRunner().invoke(
        vm, _create_args("--pricing-id", _PRICING_UUID), obj=_app(client)
    )
    assert result.exit_code != 0
    assert "not a VM pricing" in result.output


def test_vm_create_requires_instance_type_or_pricing_id():
    client = MagicMock()
    result = CliRunner().invoke(vm, _create_args(), obj=_app(client))
    assert result.exit_code != 0
    assert "either --instance-type or --pricing-id" in result.output


def test_vm_create_no_pricing_match_errors():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.list_pricings.return_value = []

    result = CliRunner().invoke(
        vm, _create_args("--instance-type", "M-8"), obj=_app(client)
    )
    assert result.exit_code != 0
    assert "no ondemand pricing for instance type" in result.output


def test_vm_create_multiple_pricings_lists_uuid_candidates():
    client = MagicMock()
    client.list_instance_types.return_value = [{"id": _IT_UUID, "name": "M-8"}]
    client.list_pricings.return_value = [
        {"id": "p-uuid-1", "resource_id": _IT_UUID, "pricing_type": "ondemand"},
        {"id": "p-uuid-2", "resource_id": _IT_UUID, "pricing_type": "ondemand"},
    ]

    result = CliRunner().invoke(
        vm, _create_args("--instance-type", "M-8"), obj=_app(client)
    )
    assert result.exit_code != 0
    assert "multiple ondemand pricings" in result.output
    assert "p-uuid-1" in result.output
    assert "p-uuid-2" in result.output
    assert "--pricing-id" in result.output


def test_vm_update_no_fields_errors():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]

    runner = CliRunner()
    result = runner.invoke(vm, ["update", "demo"], obj=_app(client))
    assert result.exit_code != 0
    assert "nothing to update" in result.output
    client.update_vm.assert_not_called()


def test_vm_update_patches_resolved_fields():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_pricings.return_value = [{"id": "p-2", "name": "M-16"}]
    client.update_vm.return_value = {"id": "vm-1"}

    runner = CliRunner()
    result = runner.invoke(
        vm,
        ["update", "demo", "--pricing", "M-16", "--always-on"],
        obj=_app(client),
    )
    assert result.exit_code == 0, result.output
    client.update_vm.assert_called_once()
    args, kwargs = client.update_vm.call_args
    assert args[0] == "vm-1"
    assert kwargs["pricing_id"] == "p-2"
    assert kwargs["always_on"] is True


def test_vm_delete_cascade_cleans_up_attached_resources():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_allocations.return_value = []  # already idle
    nics = [{"id": "nic-1", "attached_machine_id": "vm-1"}]
    ips = [{"id": "ip-1", "attached_network_interface_id": "nic-1"}]
    bss = [{"id": "bs-1", "attached_machine_id": "vm-1"}]
    client.list_nics.return_value = nics
    client.list_public_ips.return_value = ips
    client.list_block_storages.return_value = bss
    client.delete_vm.return_value = {"id": "vm-1"}

    runner = CliRunner()
    result = runner.invoke(vm, ["delete", "demo", "--cascade", "-y"], obj=_app(client))
    assert result.exit_code == 0, result.output

    client.delete_allocation.assert_not_called()
    client.wait_for_status.assert_not_called()
    client.attach_public_ip.assert_called_once_with("ip-1", None)
    client.delete_public_ip.assert_called_once_with("ip-1")
    client.attach_nic.assert_called_once_with("nic-1", None)
    client.delete_nic.assert_called_once_with("nic-1")
    client.attach_block_storage.assert_called_once_with("bs-1", None)
    client.delete_block_storage.assert_called_once_with("bs-1")
    client.delete_vm.assert_called_once_with("vm-1")


def test_vm_delete_cascade_stops_running_vm_first():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_allocations.return_value = [
        {"id": "a-old", "status": "terminated"},
        {"id": "a-active", "status": "started"},
    ]
    client.list_nics.return_value = []
    client.list_public_ips.return_value = []
    client.list_block_storages.return_value = []
    client.delete_vm.return_value = {"id": "vm-1"}

    runner = CliRunner()
    result = runner.invoke(vm, ["delete", "demo", "--cascade", "-y"], obj=_app(client))
    assert result.exit_code == 0, result.output

    client.delete_allocation.assert_called_once_with("a-active")
    client.wait_for_status.assert_called_once()
    target = client.wait_for_status.call_args.args[1]
    assert target == {"idle"}
    client.delete_vm.assert_called_once_with("vm-1")
    assert "Stopping demo" in result.output
    assert "Waiting for VM to become idle" in result.output


def test_vm_delete_aborts_without_yes_when_no_input():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]

    runner = CliRunner()
    result = runner.invoke(vm, ["delete", "demo"], input="n\n", obj=_app(client))
    assert result.exit_code != 0
    client.delete_vm.assert_not_called()


def test_vm_delete_no_cascade_skips_cleanup():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.delete_vm.return_value = {"id": "vm-1"}

    runner = CliRunner()
    result = runner.invoke(
        vm, ["delete", "demo", "-y", "--no-cascade"], obj=_app(client)
    )
    assert result.exit_code == 0
    client.list_nics.assert_not_called()
    client.list_block_storages.assert_not_called()
    client.delete_vm.assert_called_once_with("vm-1")


def test_vm_delete_default_does_not_cascade():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.delete_vm.return_value = {"id": "vm-1"}

    runner = CliRunner()
    result = runner.invoke(vm, ["delete", "demo", "-y"], obj=_app(client))
    assert result.exit_code == 0, result.output
    client.list_nics.assert_not_called()
    client.list_block_storages.assert_not_called()
    client.list_public_ips.assert_not_called()
    client.delete_vm.assert_called_once_with("vm-1")


def test_vm_start_creates_allocation():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.create_allocation.return_value = {"id": "alloc-1"}

    runner = CliRunner()
    result = runner.invoke(vm, ["start", "demo"], obj=_app(client))
    assert result.exit_code == 0, result.output
    client.create_allocation.assert_called_once_with("vm-1")


def test_vm_stop_deletes_active_allocation():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_allocations.return_value = [
        {"id": "a-old", "status": "terminated"},
        {"id": "a-active", "status": "started"},
    ]
    client.delete_allocation.return_value = {"id": "a-active"}

    runner = CliRunner()
    result = runner.invoke(vm, ["stop", "demo"], obj=_app(client))
    assert result.exit_code == 0, result.output
    client.delete_allocation.assert_called_once_with("a-active")


def test_vm_stop_errors_when_no_allocations():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_allocations.return_value = []

    runner = CliRunner()
    result = runner.invoke(vm, ["stop", "demo"], obj=_app(client))
    assert result.exit_code != 0
    assert "no active allocation" in result.output


def test_vm_stop_errors_when_only_inactive_allocations():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_allocations.return_value = [
        {"id": "a1", "status": "terminated"},
        {"id": "a2", "status": "queued"},
    ]

    runner = CliRunner()
    result = runner.invoke(vm, ["stop", "demo"], obj=_app(client))
    assert result.exit_code != 0
    assert "already terminated" in result.output
    client.delete_allocation.assert_not_called()


def test_vm_get_json_includes_attached_resources():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.get_vm.return_value = {"id": "vm-1", "name": "demo", "status": "started"}
    client.list_block_storages.return_value = [
        {"id": "bs-1", "name": "demo-disk", "size_gib": 100, "status": "prepared"}
    ]
    client.list_nics.return_value = [
        {"id": "nic-1", "name": "demo-nic", "ip": "10.0.0.5", "status": "ready"}
    ]
    client.list_public_ips.return_value = [
        {"id": "ip-1", "ip": "1.2.3.4", "attached_network_interface_id": "nic-1"},
        {"id": "ip-2", "ip": "5.6.7.8", "attached_network_interface_id": "other"},
    ]

    runner = CliRunner()
    result = runner.invoke(vm, ["demo", "--format", "json"], obj=_app(client))
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert data["name"] == "demo"
    assert [bs["name"] for bs in data["attached_block_storages"]] == ["demo-disk"]
    assert [n["name"] for n in data["attached_nics"]] == ["demo-nic"]
    assert [ip["ip"] for ip in data["attached_public_ips"]] == ["1.2.3.4"]

    client.list_block_storages.assert_called_once_with(attached_machine_id="vm-1")
    client.list_nics.assert_called_once_with(attached_machine_id="vm-1")


def test_vm_get_table_renders_section_headers():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.get_vm.return_value = {"id": "vm-1", "name": "demo", "status": "started"}
    client.list_block_storages.return_value = [
        {"id": "bs-1", "name": "demo-disk", "size_gib": 100, "status": "prepared"}
    ]
    client.list_nics.return_value = [
        {"id": "nic-1", "name": "demo-nic", "ip": "10.0.0.5"}
    ]
    client.list_public_ips.return_value = [
        {"id": "ip-1", "ip": "1.2.3.4", "attached_network_interface_id": "nic-1"}
    ]

    runner = CliRunner()
    result = runner.invoke(vm, ["demo"], obj=_app(client))
    assert result.exit_code == 0, result.output
    assert "Attached block storages" in result.output
    assert "Attached NICs" in result.output
    assert "Attached public IPs" in result.output


def test_vm_get_skips_empty_sections():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.get_vm.return_value = {"id": "vm-1", "name": "demo", "status": "stopped"}
    client.list_block_storages.return_value = []
    client.list_nics.return_value = []

    runner = CliRunner()
    result = runner.invoke(vm, ["demo"], obj=_app(client))
    assert result.exit_code == 0, result.output
    assert "Attached block storages" not in result.output
    assert "Attached NICs" not in result.output
    assert "Attached public IPs" not in result.output
    client.list_public_ips.assert_not_called()


def test_vm_list_includes_attached_public_ips_in_table():
    client = MagicMock()
    client.list_vms.return_value = [
        {"id": "vm-1", "name": "demo", "status": "started"},
        {"id": "vm-2", "name": "other", "status": "idle"},
    ]
    client.list_nics.return_value = [
        {"id": "nic-1", "attached_machine_id": "vm-1"},
        {"id": "nic-2", "attached_machine_id": "vm-1"},
        {"id": "nic-3", "attached_machine_id": "vm-2"},
        {"id": "nic-4", "attached_machine_id": None},
    ]
    client.list_public_ips.return_value = [
        {"id": "ip-1", "ip": "1.2.3.4", "attached_network_interface_id": "nic-1"},
        {"id": "ip-2", "ip": "5.6.7.8", "attached_network_interface_id": "nic-2"},
        {"id": "ip-3", "ip": "9.9.9.9", "attached_network_interface_id": "nic-4"},
    ]

    result = CliRunner().invoke(vm, ["list"], obj=_app(client))
    assert result.exit_code == 0, result.output
    assert "1.2.3.4" in result.output
    assert "5.6.7.8" in result.output
    assert "9.9.9.9" not in result.output
    assert "public_ip" in result.output


def test_vm_list_json_attaches_public_ip_field():
    client = MagicMock()
    client.list_vms.return_value = [
        {"id": "vm-1", "name": "demo", "status": "started"},
    ]
    client.list_nics.return_value = [{"id": "nic-1", "attached_machine_id": "vm-1"}]
    client.list_public_ips.return_value = [
        {"id": "ip-1", "ip": "1.2.3.4", "attached_network_interface_id": "nic-1"}
    ]

    result = CliRunner().invoke(vm, ["list", "--format", "json"], obj=_app(client))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data[0]["public_ip"] == "1.2.3.4"


def test_vm_list_handles_no_public_ips():
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.list_nics.return_value = []
    client.list_public_ips.return_value = []

    result = CliRunner().invoke(vm, ["list"], obj=_app(client))
    assert result.exit_code == 0, result.output


def test_vm_list_skips_lookups_when_empty():
    client = MagicMock()
    client.list_vms.return_value = []

    result = CliRunner().invoke(vm, ["list"], obj=_app(client))
    assert result.exit_code == 0, result.output
    client.list_nics.assert_not_called()
    client.list_public_ips.assert_not_called()
