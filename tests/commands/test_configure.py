from __future__ import annotations

from unittest.mock import MagicMock

import yaml
from click.testing import CliRunner

from app.commands import configure as configure_module
from app.commands.configure import (
    config_group,
    config_init,
    config_set,
    config_show,
    config_verify,
)


def test_config_init_writes_prompted_values(isolated_config_path, monkeypatch):
    _, path = isolated_config_path

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "central-01-a"}
    ]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake_client)

    runner = CliRunner()
    result = runner.invoke(config_init, input="1\nsecret-token\n")
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["api_endpoint"] == "https://portal.elice.cloud/api"
    assert saved["api_token"] == "secret-token"
    assert saved["zone_id"] == "11111111-1111-1111-1111-111111111111"


def test_config_init_picks_gov_endpoint(isolated_config_path, monkeypatch):
    _, path = isolated_config_path

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [
        {"id": "22222222-2222-2222-2222-222222222222", "name": "central-01-a"}
    ]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake_client)

    runner = CliRunner()
    result = runner.invoke(config_init, input="2\nsecret-token\n")
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load(path.read_text())
    assert saved["api_endpoint"] == "https://portal.gov.elice.cloud/api"


def test_config_set_top_level_writes_string(isolated_config_path):
    _, path = isolated_config_path
    runner = CliRunner()
    result = runner.invoke(config_set, ["api_token", "abc"])
    assert result.exit_code == 0, result.output
    assert "set api_token" in result.output
    assert yaml.safe_load(path.read_text())["api_token"] == "abc"


def test_config_set_stores_values_as_strings(isolated_config_path):
    _, path = isolated_config_path
    runner = CliRunner()
    runner.invoke(config_set, ["vm_defaults.size", "100"])
    runner.invoke(config_set, ["vm_defaults.always_on", "true"])
    saved = yaml.safe_load(path.read_text())
    assert saved["vm_defaults"]["size"] == "100"
    assert saved["vm_defaults"]["always_on"] == "true"


def test_config_set_does_not_coerce_numeric_token(isolated_config_path):
    _, path = isolated_config_path
    runner = CliRunner()
    runner.invoke(config_set, ["api_token", "0123456789"])
    saved = yaml.safe_load(path.read_text())
    assert saved["api_token"] == "0123456789"


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


def test_config_group_set_subcommand_via_group(isolated_config_path):
    runner = CliRunner()
    result = runner.invoke(config_group, ["set", "api_token", "tok"])
    assert result.exit_code == 0


def _write_full_config(path, **extra) -> None:
    base = {
        "api_endpoint": "https://api.example/api",
        "api_token": "tok",
        "zone_id": "11111111-1111-1111-1111-111111111111",
    }
    base.update(extra)
    path.write_text(yaml.safe_dump(base))


def test_config_verify_reports_missing_required_fields(isolated_config_path):
    _, path = isolated_config_path
    path.write_text(yaml.safe_dump({"api_endpoint": "e"}))
    result = CliRunner().invoke(config_verify)
    assert result.exit_code != 0
    assert "api_token: not set" in result.output
    assert "zone_id: not set" in result.output


def test_config_verify_reports_auth_failure(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(path)

    from app.client import ECIError

    fake = MagicMock()
    fake.organization.side_effect = ECIError(401, "unauthorized", "bad token")
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code != 0
    assert "auth: " in result.output
    assert "authentication failed" in result.output


def test_config_verify_validates_zone_uuid_exists(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(path)

    fake = MagicMock()
    fake.organization.return_value = {"name": "elice"}
    fake.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "kr-central"}
    ]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code == 0, result.output
    assert "zone: kr-central" in result.output
    assert "all checks passed" in result.output


def test_config_verify_reports_unknown_zone_uuid(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(path)

    fake = MagicMock()
    fake.organization.return_value = {"name": "elice"}
    fake.list_zones.return_value = [{"id": "other-zone", "name": "other"}]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code != 0
    assert "zone_id" in result.output
    assert "not found" in result.output


def test_config_verify_validates_vm_defaults_specs(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(
        path,
        vm_defaults={
            "good": {"pricing": "M-8", "image": "ubuntu", "subnet": "default"},
        },
    )

    fake = MagicMock()
    fake.organization.return_value = {"name": "elice"}
    fake.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "kr-central"}
    ]
    fake.list_pricings.return_value = [{"id": "p-1", "name": "M-8"}]
    fake.list_images.return_value = [{"id": "img-1", "name": "ubuntu"}]
    fake.list_subnets.return_value = [{"id": "sn-1", "name": "default"}]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code == 0, result.output
    assert "vm_defaults.good" in result.output


def test_config_verify_flags_unresolvable_spec_field(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(
        path,
        vm_defaults={"broken": {"pricing": "ghost-pricing"}},
    )

    fake = MagicMock()
    fake.organization.return_value = {"name": "elice"}
    fake.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "kr-central"}
    ]
    fake.list_pricings.return_value = []
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code != 0
    assert "vm_defaults.broken" in result.output
    assert "ghost-pricing" in result.output


def test_config_verify_flags_corrupted_string_field(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(
        path,
        vm_defaults={"bad": {"image": 12345}},
    )

    fake = MagicMock()
    fake.organization.return_value = {"name": "elice"}
    fake.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "kr-central"}
    ]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code != 0
    assert "image=12345" in result.output
    assert "must be a string" in result.output


def test_config_verify_flags_corrupted_size_gib(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_full_config(
        path,
        vm_defaults={"bad": {"size_gib": "100"}},
    )

    fake = MagicMock()
    fake.organization.return_value = {"name": "elice"}
    fake.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "kr-central"}
    ]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake)

    result = CliRunner().invoke(config_verify)
    assert result.exit_code != 0
    assert "size_gib='100'" in result.output
    assert "must be an int" in result.output
