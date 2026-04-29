from __future__ import annotations

import json

import pytest

from app.client import (
    ECIClient,
    ECIError,
    PAGE_SIZE,
    _coerce_filter,
    _ilike,
)
from app.config import Config


def test_ilike_wraps_plain_string():
    assert _ilike("foo") == "%foo%"


def test_ilike_passes_through_when_already_wildcarded():
    assert _ilike("foo%") == "foo%"
    assert _ilike("%foo") == "%foo"


def test_coerce_filter_name_ilike_wraps():
    assert _coerce_filter("name_ilike", "abc") == "%abc%"


def test_coerce_filter_bool_to_lowercase_string():
    assert _coerce_filter("activated", True) == "true"
    assert _coerce_filter("activated", False) == "false"


def test_coerce_filter_dict_and_list_become_json():
    assert _coerce_filter("tags", {"a": 1}) == json.dumps({"a": 1})
    assert _coerce_filter("ids", [1, 2]) == json.dumps([1, 2])


def test_coerce_filter_passes_through_other_values():
    assert _coerce_filter("anything", "raw") == "raw"
    assert _coerce_filter("count", 42) == 42


def test_eci_error_message_format():
    err = ECIError(404, "NOT_FOUND", "missing", detail={"id": "x"})
    assert err.status == 404
    assert err.code == "NOT_FOUND"
    assert "[404 NOT_FOUND] missing" in str(err)
    assert "detail=" in str(err)


def test_eci_error_without_code_or_detail():
    err = ECIError(500, None, "boom")
    assert "[500] boom" in str(err)
    assert "detail=" not in str(err)


def test_url_parsing_splits_path_prefix():
    cfg = Config(api_endpoint="https://host.example/api/v2", api_token="t")
    c = ECIClient(cfg)
    assert c.base == "https://host.example"
    assert c.path_prefix == "/api/v2"
    assert c._url("/foo") == "https://host.example/api/v2/foo"


def test_url_parsing_handles_no_path():
    cfg = Config(api_endpoint="https://host.example", api_token="t")
    c = ECIClient(cfg)
    assert c.path_prefix == ""
    assert c._url("/foo") == "https://host.example/foo"


def test_session_sets_auth_headers():
    cfg = Config(api_endpoint="https://e", api_token="abc")
    c = ECIClient(cfg)
    assert c.session.headers["Authorization"] == "Bearer abc"
    assert c.session.headers["Content-Type"] == "application/json"


def test_zone_id_property_raises_when_unset():
    cfg = Config(api_endpoint="https://e", api_token="t", zone_id="")
    c = ECIClient(cfg)
    with pytest.raises(RuntimeError, match="zone_id is not configured"):
        _ = c.zone_id


def test_request_returns_json_on_success(client, make_resp):
    client.session.request.return_value = make_resp(200, json_body={"ok": True})
    assert client.get("/path") == {"ok": True}
    client.session.request.assert_called_once()


def test_request_returns_none_on_204(client, make_resp):
    resp = make_resp(204)
    resp.content = b""
    client.session.request.return_value = resp
    assert client.delete("/x") is None


def test_request_raises_eci_error_on_4xx(client, make_resp):
    client.session.request.return_value = make_resp(
        404, json_body={"code": "NOT_FOUND", "message": "missing"}
    )
    with pytest.raises(ECIError) as exc:
        client.get("/x")
    assert exc.value.status == 404
    assert exc.value.code == "NOT_FOUND"


def test_request_falls_back_to_text_when_body_not_json(client, make_resp):
    resp = make_resp(500)
    resp.json.side_effect = ValueError("not json")
    resp.text = "internal error"
    resp.content = b"internal error"
    client.session.request.return_value = resp
    with pytest.raises(ECIError) as exc:
        client.get("/x")
    assert exc.value.status == 500
    assert "internal error" in exc.value.message


def test_paginate_collects_until_short_page(client, make_resp):
    page1 = [{"id": str(i)} for i in range(PAGE_SIZE)]
    page2 = [{"id": "last"}]
    client.session.request.side_effect = [
        make_resp(200, json_body=page1),
        make_resp(200, json_body=page2),
    ]
    out = client._paginate("/items")
    assert len(out) == PAGE_SIZE + 1
    assert client.session.request.call_count == 2

    second_call = client.session.request.call_args_list[1]
    assert second_call.kwargs["params"]["skip"] == PAGE_SIZE
    assert second_call.kwargs["params"]["count"] == PAGE_SIZE


def test_filters_includes_zone_by_default(client):
    params = client._filters(name_ilike="abc")
    assert params["filter_zone_id"] == client.zone_id
    assert params["filter_name_ilike"] == "%abc%"


def test_filters_omits_zone_when_include_zone_false(client):
    params = client._filters(include_zone=False, name_ilike="abc")
    assert "filter_zone_id" not in params


def test_filters_skips_none_values(client):
    params = client._filters(name_ilike=None, status="ready")
    assert "filter_name_ilike" not in params
    assert params["filter_status"] == "ready"


def test_filters_explicit_zone_id_suppresses_default(client):
    params = client._filters(zone_id="zzz")
    assert params["filter_zone_id"] == "zzz"


def test_create_vm_posts_expected_body(client, make_resp):
    client.session.request.return_value = make_resp(200, json_body={"id": "v1"})
    client.create_vm(
        name="vm1",
        instance_type_id="it",
        pricing_id="p",
        username="u",
        password="pw",
    )
    call = client.session.request.call_args
    assert call.args[0] == "POST"
    body = call.kwargs["json"]
    assert body["name"] == "vm1"
    assert body["zone_id"] == client.zone_id
    assert body["always_on"] is False
    assert body["tags"] == {}


def test_find_pricing_returns_exact_match(client, make_resp):
    candidates = [
        {"id": "p1", "name": "small"},
        {"id": "p2", "name": "small-extra"},
    ]
    client.session.request.return_value = make_resp(200, json_body=candidates)
    result = client.find_pricing("small", resource_kind="vm")
    assert result["id"] == "p1"


def test_find_pricing_raises_when_no_exact(client, make_resp):
    client.session.request.return_value = make_resp(
        200, json_body=[{"id": "p1", "name": "small-extra"}]
    )
    with pytest.raises(ECIError) as exc:
        client.find_pricing("small")
    assert exc.value.status == 404


def test_list_allocations_renames_vm_id_to_machine_id(client, make_resp):
    client.session.request.return_value = make_resp(200, json_body=[])
    client.list_allocations(vm_id="vm-1")
    call = client.session.request.call_args
    params = call.kwargs["params"]
    assert "filter_machine_id" in params
    assert "filter_vm_id" not in params


def test_list_vms_replaces_allocated_status_with_allocation_status(client, make_resp):
    vms = [
        {"id": "v1", "name": "a", "status": "allocated"},
        {"id": "v2", "name": "b", "status": "stopped"},
        {"id": "v3", "name": "c", "status": "allocated"},
    ]
    allocs = [
        {"id": "a1", "machine_id": "v1", "status": "started"},
        {"id": "a2", "machine_id": "v3", "status": "taken"},
        {"id": "a3", "machine_id": "v1", "status": "terminated"},
    ]
    client.session.request.side_effect = [
        make_resp(200, json_body=vms),
        make_resp(200, json_body=allocs),
    ]
    out = client.list_vms()
    by_id = {vm["id"]: vm["status"] for vm in out}
    assert by_id["v1"] == "started"
    assert by_id["v2"] == "stopped"
    assert by_id["v3"] == "taken"


def test_list_vms_skips_allocation_lookup_when_none_allocated(client, make_resp):
    vms = [{"id": "v1", "name": "a", "status": "stopped"}]
    client.session.request.return_value = make_resp(200, json_body=vms)
    out = client.list_vms()
    assert out[0]["status"] == "stopped"
    assert client.session.request.call_count == 1


def test_list_vms_keeps_allocated_when_only_inactive_allocations(client, make_resp):
    vms = [{"id": "v1", "name": "a", "status": "allocated"}]
    allocs = [
        {"id": "a1", "machine_id": "v1", "status": "queued"},
        {"id": "a2", "machine_id": "v1", "status": "terminated"},
    ]
    client.session.request.side_effect = [
        make_resp(200, json_body=vms),
        make_resp(200, json_body=allocs),
    ]
    out = client.list_vms()
    assert out[0]["status"] == "allocated"


def test_get_vm_replaces_allocated_status(client, make_resp):
    client.session.request.side_effect = [
        make_resp(200, json_body={"id": "v1", "name": "a", "status": "allocated"}),
        make_resp(
            200,
            json_body=[{"id": "a1", "machine_id": "v1", "status": "started"}],
        ),
    ]
    out = client.get_vm("v1")
    assert out["status"] == "started"


def test_get_vm_skips_lookup_when_not_allocated(client, make_resp):
    client.session.request.return_value = make_resp(
        200, json_body={"id": "v1", "name": "a", "status": "stopped"}
    )
    out = client.get_vm("v1")
    assert out["status"] == "stopped"
    assert client.session.request.call_count == 1


def test_wait_for_status_returns_when_target_reached(monkeypatch):
    from app import client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)
    cfg = Config(api_endpoint="https://e", api_token="t")
    c = ECIClient(cfg)

    states = iter([{"status": "pending"}, {"status": "ready"}])
    result = c.wait_for_status(lambda: next(states), {"ready"}, timeout=5, interval=0)
    assert result == {"status": "ready"}


def test_wait_for_status_times_out(monkeypatch):
    from app import client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)
    fake_now = iter([0.0, 0.5, 1.5, 99.0])
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(fake_now))

    cfg = Config(api_endpoint="https://e", api_token="t")
    c = ECIClient(cfg)
    with pytest.raises(TimeoutError):
        c.wait_for_status(
            lambda: {"status": "pending"}, {"ready"}, timeout=1, interval=0
        )
