from __future__ import annotations

from unittest.mock import MagicMock

import click
import pytest
import yaml
from click.testing import CliRunner

from app import cli as cli_module
from app.cli import cli, main
from app.client import ECIError


def _write_config(path, **fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(fields))


def test_cli_help_does_not_require_token(isolated_config_path):
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Elice Cloud Infrastructure" in result.output


def test_cli_exits_2_without_api_token(isolated_config_path):
    result = CliRunner().invoke(cli, ["zone"])
    assert result.exit_code == 2


def test_cli_configure_subcommand_skips_token_check(isolated_config_path):
    _, path = isolated_config_path
    result = CliRunner().invoke(
        cli, ["configure"], input="https://e/api\ntoken\nzone-uuid\n"
    )
    assert result.exit_code == 0
    assert path.exists()


def test_cli_config_show_skips_token_check(isolated_config_path):
    result = CliRunner().invoke(cli, ["config", "show"])
    assert result.exit_code == 0


def test_cli_normal_path_creates_app_context(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_config(path, api_token="t", api_endpoint="https://e/api", zone_id="z")

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [{"id": "z", "name": "kr-central"}]
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["zone", "--format", "json"])
    assert result.exit_code == 0, result.output


def test_cli_zone_override_resolves_name(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_config(path, api_token="t", api_endpoint="https://e/api", zone_id="old")

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [{"id": "new-uuid", "name": "new-zone"}]
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(
        cli, ["--zone", "new-zone", "zone", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert fake_client.config.zone_id == "new-uuid"


def test_cli_zone_override_not_found_exits_2(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_config(path, api_token="t", api_endpoint="https://e/api", zone_id="old")

    fake_client = MagicMock()
    fake_client.list_zones.return_value = []
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["--zone", "missing", "zone"])
    assert result.exit_code == 2


def test_cli_zone_override_eci_error_exits_2(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_config(path, api_token="t", api_endpoint="https://e/api", zone_id="old")

    fake_client = MagicMock()
    fake_client.list_zones.side_effect = ECIError(500, None, "boom")
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["--zone", "anything", "zone"])
    assert result.exit_code == 2


def _patch_cli_main(monkeypatch, side_effect) -> None:
    def fake_main(**kwargs):
        side_effect()

    monkeypatch.setattr(cli_module.cli, "main", fake_main)


def test_main_runs_normally(monkeypatch):
    _patch_cli_main(monkeypatch, lambda: None)
    main()  # no SystemExit on happy path


def test_main_handles_click_exception(monkeypatch):
    def boom():
        raise click.ClickException("boom")

    _patch_cli_main(monkeypatch, boom)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_main_handles_abort(monkeypatch):
    def boom():
        raise click.exceptions.Abort()

    _patch_cli_main(monkeypatch, boom)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 130


def test_main_handles_eci_error(monkeypatch):
    def boom():
        raise ECIError(500, None, "boom")

    _patch_cli_main(monkeypatch, boom)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_main_handles_broken_pipe(monkeypatch):
    def boom():
        raise BrokenPipeError()

    _patch_cli_main(monkeypatch, boom)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_main_handles_generic_exception(monkeypatch):
    def boom():
        raise ValueError("unexpected")

    _patch_cli_main(monkeypatch, boom)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
