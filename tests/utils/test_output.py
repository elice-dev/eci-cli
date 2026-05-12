from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.utils.name_resolver import NameResolver
from app.utils.output import (
    _columns_from_query,
    _full_columns,
    _project_row,
    _resolve_row_for_json,
    _stringify,
    render_list,
    render_one,
)


def test_stringify_handles_none():
    assert _stringify(None) == ""


def test_stringify_handles_bool():
    assert _stringify(True) == "true"
    assert _stringify(False) == "false"


def test_stringify_handles_dict_and_list_as_json():
    assert _stringify({"a": 1}) == json.dumps({"a": 1}, ensure_ascii=False)
    assert _stringify([1, 2]) == json.dumps([1, 2], ensure_ascii=False)


def test_stringify_handles_other_types():
    assert _stringify(42) == "42"
    assert _stringify("hello") == "hello"


def test_columns_from_query_splits_and_strips():
    assert _columns_from_query("a, b ,c") == ["a", "b", "c"]
    assert _columns_from_query("a,,b") == ["a", "b"]


def test_full_columns_strips_id_suffix_for_known_fields():
    item = {"id": "x", "name": "n", "zone_id": "z", "raw": 1}
    cols = _full_columns(item)
    assert "id" not in cols
    assert "zone" in cols
    assert "name" in cols
    assert "raw" in cols


def test_project_row_uses_resolver_for_id_columns():
    resolver = MagicMock(spec=NameResolver)
    resolver.lookup.return_value = "kr-central"
    row = {"name": "vm1", "zone_id": "uuid-1"}
    out = _project_row(row, ["name", "zone"], resolver)
    assert out == {"name": "vm1", "zone": "kr-central"}
    resolver.lookup.assert_called_once_with("zone_id", "uuid-1")


def test_project_row_blanks_missing_columns():
    resolver = MagicMock(spec=NameResolver)
    out = _project_row({"name": "x"}, ["name", "missing"], resolver)
    assert out == {"name": "x", "missing": ""}


def test_resolve_row_for_json_strips_id_suffix():
    resolver = MagicMock(spec=NameResolver)
    resolver.lookup.return_value = "kr-central"
    out = _resolve_row_for_json({"zone_id": "uuid-1", "name": "vm1"}, resolver)
    assert out == {"zone": "kr-central", "name": "vm1"}


def test_render_list_json_with_query(capsys):
    resolver = MagicMock(spec=NameResolver)
    items = [{"name": "vm1", "status": "ready"}, {"name": "vm2", "status": "pending"}]
    render_list(
        items, default_columns=["name"], fmt="json", query="name", resolver=resolver
    )
    out = capsys.readouterr().out
    assert json.loads(out) == [{"name": "vm1"}, {"name": "vm2"}]


def test_render_list_csv(capsys):
    resolver = MagicMock(spec=NameResolver)
    items = [{"id": "vm-uuid-1", "name": "vm1", "status": "ready"}]
    render_list(
        items,
        default_columns=["name", "status"],
        fmt="csv",
        query=None,
        resolver=resolver,
    )
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0] == "id,name,status"
    assert out[1] == "vm-uuid-1,vm1,ready"


def test_render_list_csv_respects_explicit_query(capsys):
    resolver = MagicMock(spec=NameResolver)
    items = [{"id": "vm-uuid-1", "name": "vm1", "status": "ready"}]
    render_list(
        items,
        default_columns=["name", "status"],
        fmt="csv",
        query="name,status",
        resolver=resolver,
    )
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0] == "name,status"
    assert out[1] == "vm1,ready"


def test_render_one_json(capsys):
    resolver = MagicMock(spec=NameResolver)
    resolver.lookup.return_value = "kr-central"
    render_one(
        {"name": "vm1", "zone_id": "uuid-1"},
        fmt="json",
        query=None,
        resolver=resolver,
    )
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {"name": "vm1", "zone": "kr-central"}
