from __future__ import annotations

import csv
import io
import json
from typing import Any, Sequence

import click
from rich.console import Console
from rich.table import Table

from .name_resolver import NameResolver

console = Console()
err_console = Console(stderr=True)


def _project_row(row: dict, columns: Sequence[str], resolver: NameResolver) -> dict:
    out: dict[str, Any] = {}
    for col in columns:
        if col in row:
            out[col] = row[col]
            continue
        id_key = f"{col}_id"
        if id_key in row and id_key in NameResolver.FIELD_MAP:
            out[col] = resolver.lookup(id_key, row.get(id_key))
        else:
            out[col] = ""

    return out


def _resolve_row_for_json(row: dict, resolver: NameResolver) -> dict:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in NameResolver.FIELD_MAP:
            out[k[:-3]] = resolver.lookup(k, v)
        else:
            out[k] = v

    return out


def _full_columns(item: dict) -> list[str]:
    cols: list[str] = []
    for k in item.keys():
        if k == "id":
            continue

        if k in NameResolver.FIELD_MAP:
            cols.append(k[:-3])
        else:
            cols.append(k)

    return cols


def _columns_from_query(query: str) -> list[str]:
    return [c.strip() for c in query.split(",") if c.strip()]


def _stringify(v: Any) -> str:
    if v is None:
        return ""

    if isinstance(v, bool):
        return "true" if v else "false"

    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)

    return str(v)


def _emit_table(
    rows: list[dict],
    headers: Sequence[str],
    labels: dict[str, str] | None = None,
) -> None:
    table = Table(show_lines=False)
    labels = labels or {}

    for h in headers:
        table.add_column(labels.get(h, h), overflow="fold")

    for r in rows:
        table.add_row(*[_stringify(r.get(h, "")) for h in headers])

    console.print(table)


def _emit_json(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _emit_csv(
    rows: list[dict],
    headers: Sequence[str],
    labels: dict[str, str] | None = None,
) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    labels = labels or {}
    w.writerow([labels.get(h, h) for h in headers])

    for r in rows:
        w.writerow([_stringify(r.get(h, "")) for h in headers])

    click.echo(buf.getvalue().rstrip("\n"))


def render_list(
    items: list[dict],
    *,
    default_columns: Sequence[str],
    fmt: str,
    query: str | None,
    resolver: NameResolver,
    column_labels: dict[str, str] | None = None,
) -> None:
    if query:
        cols = _columns_from_query(query)
    else:
        cols = list(default_columns)
        if "id" not in cols:
            cols.insert(0, "id")

    if fmt == "json":
        _emit_json(
            [_project_row(it, cols, resolver) for it in items]
            if query
            else [_resolve_row_for_json(it, resolver) for it in items]
        )
        return

    rows = [_project_row(it, cols, resolver) for it in items]

    if fmt == "csv":
        _emit_csv(rows, cols, column_labels)
    else:
        _emit_table(rows, cols, column_labels)


def render_one(
    item: dict,
    *,
    fmt: str,
    query: str | None,
    resolver: NameResolver,
) -> None:
    cols = _columns_from_query(query) if query else _full_columns(item)
    if fmt == "json":
        _emit_json(
            _project_row(item, cols, resolver)
            if query
            else _resolve_row_for_json(item, resolver)
        )
        return

    row = _project_row(item, cols, resolver)

    if fmt == "csv":
        _emit_csv([row], cols)
    else:
        table = Table(show_header=False)
        table.add_column("field", style="bold")
        table.add_column("value", overflow="fold")
        for c in cols:
            table.add_row(c, _stringify(row.get(c, "")))
        console.print(table)


def emit_action_result(item: Any) -> None:
    if item is None:
        click.echo("ok")
        return

    _emit_json(item)
