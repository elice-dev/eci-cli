from __future__ import annotations

from unittest.mock import MagicMock

import click
import pytest

from app.utils.name_resolver import AppContext, NameResolver, is_uuid


def test_is_uuid_accepts_valid():
    assert is_uuid("11111111-1111-1111-1111-111111111111")


def test_is_uuid_rejects_garbage():
    assert not is_uuid("not-a-uuid")
    assert not is_uuid("")
    assert not is_uuid("12345")


def _client_with(list_fn: str, items: list[dict]) -> MagicMock:
    client = MagicMock()
    getattr(client, list_fn).return_value = items
    getattr(client, list_fn).side_effect = None
    return client


def test_lookup_returns_value_when_field_unknown():
    client = MagicMock()
    r = NameResolver(client)
    assert r.lookup("not_in_field_map", "x") == "x"


def test_lookup_returns_value_when_empty():
    client = MagicMock()
    r = NameResolver(client)
    assert r.lookup("zone_id", "") == ""
    assert r.lookup("zone_id", None) is None


def test_lookup_resolves_id_to_name_and_caches():
    client = MagicMock()
    client.list_zones.return_value = [{"id": "uuid-1", "name": "kr-central"}]
    r = NameResolver(client)
    assert r.lookup("zone_id", "uuid-1") == "kr-central"
    r.lookup("zone_id", "uuid-1")
    assert client.list_zones.call_count == 1


def test_lookup_falls_back_to_value_on_client_error():
    client = MagicMock()
    client.list_zones.side_effect = RuntimeError("network down")
    r = NameResolver(client)
    assert r.lookup("zone_id", "uuid-1") == "uuid-1"


def test_lookup_uses_ip_when_name_missing():
    client = MagicMock()
    client.list_public_ips.return_value = [{"id": "uuid-ip", "ip": "1.2.3.4"}]
    NameResolver.FIELD_MAP["ip_id_for_test"] = "list_public_ips"
    try:
        r = NameResolver(client)
        assert r.lookup("ip_id_for_test", "uuid-ip") == "1.2.3.4"
    finally:
        del NameResolver.FIELD_MAP["ip_id_for_test"]


def test_resolve_passes_through_uuid():
    client = MagicMock()
    r = NameResolver(client)
    uuid_val = "11111111-1111-1111-1111-111111111111"
    assert r.resolve("list_zones", uuid_val) == uuid_val
    client.list_zones.assert_not_called()


def test_resolve_finds_exact_match_by_name():
    client = MagicMock()
    client.list_zones.return_value = [
        {"id": "id-1", "name": "kr-central"},
        {"id": "id-2", "name": "kr-central-2"},
    ]
    r = NameResolver(client)
    assert r.resolve("list_zones", "kr-central") == "id-1"


def test_resolve_finds_exact_match_by_ip_when_name_missing():
    client = MagicMock()
    client.list_public_ips.return_value = [{"id": "id-1", "ip": "1.2.3.4"}]
    r = NameResolver(client)
    assert r.resolve("list_public_ips", "1.2.3.4") == "id-1"


def test_resolve_raises_when_no_match():
    client = MagicMock()
    client.list_zones.return_value = []
    r = NameResolver(client)
    with pytest.raises(click.ClickException, match="no item named"):
        r.resolve("list_zones", "missing")


def test_resolve_raises_when_multiple_matches():
    client = MagicMock()
    client.list_zones.return_value = [
        {"id": "id-1", "name": "dup"},
        {"id": "id-2", "name": "dup"},
    ]
    r = NameResolver(client)
    with pytest.raises(click.ClickException, match="multiple items"):
        r.resolve("list_zones", "dup")


def test_app_context_creates_resolver():
    client = MagicMock()
    ctx = AppContext(client=client)
    assert isinstance(ctx.resolver, NameResolver)
    assert ctx.resolver.client is client
