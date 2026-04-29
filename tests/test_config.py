from __future__ import annotations

import os
import stat

import pytest
import yaml


def test_load_returns_defaults_when_no_file(isolated_config_path):
    config_module, _ = isolated_config_path
    cfg = config_module.Config.load()
    assert cfg.api_endpoint == config_module.DEFAULT_ENDPOINT
    assert cfg.api_token == ""
    assert cfg.zone_id == ""
    assert cfg.vm_defaults == {}


def test_load_reads_yaml_file(isolated_config_path):
    config_module, path = isolated_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "api_endpoint": "https://example.com/api",
                "api_token": "t",
                "zone_id": "z",
                "vm_defaults": {"username": "ubuntu"},
            }
        )
    )
    cfg = config_module.Config.load()
    assert cfg.api_endpoint == "https://example.com/api"
    assert cfg.api_token == "t"
    assert cfg.zone_id == "z"
    assert cfg.vm_defaults == {"username": "ubuntu"}


def test_env_overrides_file(isolated_config_path, monkeypatch):
    config_module, path = isolated_config_path
    path.write_text(yaml.safe_dump({"api_token": "from-file"}))
    monkeypatch.setenv("ECI_API_TOKEN", "from-env")
    monkeypatch.setenv("ECI_API_ENDPOINT", "https://env.example/api")
    cfg = config_module.Config.load()
    assert cfg.api_token == "from-env"
    assert cfg.api_endpoint == "https://env.example/api"


def test_save_writes_yaml_with_secure_permissions(isolated_config_path):
    config_module, path = isolated_config_path
    cfg = config_module.Config(api_endpoint="e", api_token="t", zone_id="z")
    cfg.vm_defaults = {"username": "ubuntu"}
    cfg.save()

    assert path.exists()
    data = yaml.safe_load(path.read_text())
    assert data == {
        "api_endpoint": "e",
        "api_token": "t",
        "zone_id": "z",
        "vm_defaults": {"username": "ubuntu"},
    }
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_set_path_top_level(isolated_config_path):
    config_module, _ = isolated_config_path
    cfg = config_module.Config()
    cfg.set_path("api_token", "abc")
    assert cfg.api_token == "abc"


def test_set_path_vm_defaults_nested(isolated_config_path):
    config_module, _ = isolated_config_path
    cfg = config_module.Config()
    cfg.set_path("vm_defaults.username", "ubuntu")
    cfg.set_path("vm_defaults.network.subnet", "default")
    assert cfg.vm_defaults == {
        "username": "ubuntu",
        "network": {"subnet": "default"},
    }


def test_set_path_unsupported_raises(isolated_config_path):
    config_module, _ = isolated_config_path
    cfg = config_module.Config()
    with pytest.raises(KeyError):
        cfg.set_path("unknown.key", "x")
