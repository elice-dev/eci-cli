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


def test_cli_short_help_works_at_root(isolated_config_path):
    result = CliRunner().invoke(cli, ["-h"])
    assert result.exit_code == 0
    assert "Elice Cloud Infrastructure" in result.output


def test_cli_short_help_works_on_subcommand(isolated_config_path):
    result = CliRunner().invoke(cli, ["compute", "-h"])
    assert result.exit_code == 0
    assert "Compute resources" in result.output


def test_cli_subcommand_help_does_not_require_token(isolated_config_path):
    result = CliRunner().invoke(cli, ["compute", "vm", "--help"])
    assert result.exit_code == 0
    assert "Virtual machines" in result.output


def test_cli_exits_2_without_api_token(isolated_config_path):
    result = CliRunner().invoke(cli, ["zone"])
    assert result.exit_code == 2


def test_cli_config_init_subcommand_skips_token_check(
    isolated_config_path, monkeypatch
):
    _, path = isolated_config_path

    from app.commands import configure as configure_module
    from unittest.mock import MagicMock

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "central-01-a"}
    ]
    monkeypatch.setattr(configure_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["config", "init"], input="1\ntok\n")
    assert result.exit_code == 0, result.output
    assert path.exists()


def test_cli_config_show_skips_token_check(isolated_config_path):
    result = CliRunner().invoke(cli, ["config", "show"])
    assert result.exit_code == 0


def test_cli_normal_path_creates_app_context(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    zone_uuid = "11111111-1111-1111-1111-111111111111"
    _write_config(path, api_token="t", api_endpoint="https://e/api", zone_id=zone_uuid)

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [{"id": zone_uuid, "name": "kr-central"}]
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["zone", "--format", "json"])
    assert result.exit_code == 0, result.output


def test_cli_resolves_zone_name_from_config(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_config(
        path, api_token="t", api_endpoint="https://e/api", zone_id="kr-central"
    )

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [{"id": "z-uuid", "name": "kr-central"}]
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["zone", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert fake_client.config.zone_id == "z-uuid"


def test_cli_zone_override_resolves_name(isolated_config_path, monkeypatch):
    _, path = isolated_config_path
    _write_config(path, api_token="t", api_endpoint="https://e/api", zone_id="old")

    fake_client = MagicMock()
    fake_client.list_zones.return_value = [{"id": "new-uuid", "name": "new-zone"}]
    monkeypatch.setattr(cli_module, "ECIClient", lambda cfg: fake_client)

    result = CliRunner().invoke(cli, ["--zone", "new-zone", "zone", "--format", "json"])
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
