from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.client import ECIClient
from app.config import Config
from app.utils.name_resolver import AppContext


@pytest.fixture
def config() -> Config:
    return Config(
        api_endpoint="https://portal.example.com/api",
        api_token="token-xyz",
        zone_id="11111111-1111-1111-1111-111111111111",
    )


@pytest.fixture
def client(config: Config) -> ECIClient:
    c = ECIClient(config)
    c.session = MagicMock()
    return c


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def app_obj(mock_client: MagicMock) -> AppContext:
    return AppContext(client=mock_client)


def make_response(status: int = 200, json_body: Any = None, content: bytes | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.content = content if content is not None else (b"{}" if json_body is None else b"x")
    resp.json.return_value = json_body if json_body is not None else {}
    resp.text = "" if json_body is None else str(json_body)
    return resp


@pytest.fixture
def make_resp():
    return make_response


@pytest.fixture
def isolated_config_path(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    monkeypatch.setenv("ECI_CONFIG", str(path))
    import importlib

    import app.config as config_module

    importlib.reload(config_module)
    yield config_module, path
    importlib.reload(config_module)
