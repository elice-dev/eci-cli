from __future__ import annotations

import yaml
from click.testing import CliRunner

from app.commands.vm_spec import (
    vm_spec,
    vm_spec_delete,
    vm_spec_list,
    vm_spec_save,
    vm_spec_show,
)


def test_vm_spec_list_lists_names(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"vm_defaults": {"small": {}, "large": {}}}))
    result = CliRunner().invoke(vm_spec_list)
    assert result.exit_code == 0
    assert set(result.output.split()) == {"small", "large"}


def test_vm_spec_list_empty(isolated_config_path):
    result = CliRunner().invoke(vm_spec_list)
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_vm_spec_show_existing(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(
        yaml.safe_dump({"vm_defaults": {"a": {"instance_type": "M-8", "size_gib": 50}}})
    )
    result = CliRunner().invoke(vm_spec_show, ["a"])
    assert result.exit_code == 0
    assert "instance_type: M-8" in result.output
    assert "size_gib: 50" in result.output


def test_vm_spec_show_missing(isolated_config_path):
    result = CliRunner().invoke(vm_spec_show, ["nope"])
    assert result.exit_code != 0
    assert "no spec named" in result.output


def test_vm_spec_save_creates_new(isolated_config_path):
    _, path = isolated_config_path
    result = CliRunner().invoke(
        vm_spec_save,
        [
            "default",
            "--instance-type",
            "M-8",
            "--price-type",
            "spot",
            "--image",
            "ubuntu",
            "--size-gib",
            "100",
            "--subnet",
            "default",
            "--username",
            "ubuntu",
        ],
    )
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"]["default"] == {
        "instance_type": "M-8",
        "price_type": "spot",
        "image": "ubuntu",
        "size_gib": 100,
        "subnet": "default",
        "username": "ubuntu",
    }


def test_vm_spec_save_omits_unset_fields(isolated_config_path):
    _, path = isolated_config_path
    result = CliRunner().invoke(vm_spec_save, ["minimal", "--instance-type", "M-8"])
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"]["minimal"] == {"instance_type": "M-8"}


def test_vm_spec_save_requires_at_least_one_field(isolated_config_path):
    result = CliRunner().invoke(vm_spec_save, ["empty"])
    assert result.exit_code != 0
    assert "at least one of" in result.output


def test_vm_spec_save_refuses_overwrite_without_force(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"vm_defaults": {"a": {"instance_type": "old"}}}))
    result = CliRunner().invoke(vm_spec_save, ["a", "--instance-type", "new"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_vm_spec_save_overwrites_with_force(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"vm_defaults": {"a": {"instance_type": "old"}}}))
    result = CliRunner().invoke(
        vm_spec_save, ["a", "--instance-type", "new", "--force"]
    )
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"]["a"] == {"instance_type": "new"}


def test_vm_spec_delete_removes(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"vm_defaults": {"a": {}, "b": {}}}))
    result = CliRunner().invoke(vm_spec_delete, ["a"])
    assert result.exit_code == 0
    assert "deleted vm_defaults.a" in result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"] == {"b": {}}


def test_vm_spec_delete_missing(isolated_config_path):
    result = CliRunner().invoke(vm_spec_delete, ["ghost"])
    assert result.exit_code != 0
    assert "no spec named" in result.output


def test_vm_spec_group_show_via_subcommand(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"vm_defaults": {"a": {"instance_type": "M-8"}}}))
    result = CliRunner().invoke(vm_spec, ["show", "a"])
    assert result.exit_code == 0
    assert "instance_type: M-8" in result.output
