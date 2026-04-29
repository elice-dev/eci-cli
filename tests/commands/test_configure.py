from __future__ import annotations

import yaml
from click.testing import CliRunner

from app.commands.configure import (
    config_delete_vm_spec,
    config_group,
    config_list_vm_specs,
    config_set,
    config_show,
    config_show_vm_spec,
    configure,
)


def test_configure_writes_prompted_values(isolated_config_path):
    _, path = isolated_config_path
    runner = CliRunner()
    result = runner.invoke(
        configure,
        input="https://api.example/api\nsecret-token\nzone-uuid\n",
    )
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["api_endpoint"] == "https://api.example/api"
    assert saved["api_token"] == "secret-token"
    assert saved["zone_id"] == "zone-uuid"


def test_config_set_top_level_writes_string(isolated_config_path):
    _, path = isolated_config_path
    runner = CliRunner()
    result = runner.invoke(config_set, ["api_token", "abc"])
    assert result.exit_code == 0, result.output
    assert "set api_token" in result.output
    assert yaml.safe_load(path.read_text())["api_token"] == "abc"


def test_config_set_parses_int_and_bool(isolated_config_path):
    _, path = isolated_config_path
    runner = CliRunner()
    runner.invoke(config_set, ["vm_defaults.size", "100"])
    runner.invoke(config_set, ["vm_defaults.always_on", "true"])
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"]["size"] == 100
    assert saved["vm_defaults"]["always_on"] is True


def test_config_set_unknown_path_returns_user_error(isolated_config_path):
    runner = CliRunner()
    result = runner.invoke(config_set, ["unknown.key", "x"])
    assert result.exit_code != 0
    assert "unsupported config path" in result.output


def test_config_show_redacts_token(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(
        yaml.safe_dump({"api_endpoint": "e", "api_token": "secret", "zone_id": "z"})
    )
    runner = CliRunner()
    result = runner.invoke(config_show)
    assert result.exit_code == 0
    assert "secret" not in result.output
    assert "***" in result.output


def test_config_list_vm_specs_lists_keys(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(
        yaml.safe_dump({"vm_defaults": {"small": {}, "large": {}}})
    )
    runner = CliRunner()
    result = runner.invoke(config_list_vm_specs)
    assert result.exit_code == 0
    assert set(result.output.split()) == {"small", "large"}


def test_config_show_vm_spec_missing_errors(isolated_config_path):
    runner = CliRunner()
    result = runner.invoke(config_show_vm_spec, ["missing"])
    assert result.exit_code != 0
    assert "no spec named" in result.output


def test_config_delete_vm_spec_removes_entry(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"vm_defaults": {"a": {"k": 1}, "b": {}}}))
    runner = CliRunner()
    result = runner.invoke(config_delete_vm_spec, ["a"])
    assert result.exit_code == 0
    assert "deleted vm_defaults.a" in result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"] == {"b": {}}


def test_config_group_set_subcommand_via_group(isolated_config_path):
    runner = CliRunner()
    result = runner.invoke(config_group, ["set", "api_token", "tok"])
    assert result.exit_code == 0
