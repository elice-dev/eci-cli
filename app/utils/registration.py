from typing import Any, Callable, Sequence

import click

from .name_resolver import AppContext, NameResolver
from .options import FilterSpec
from .output import render_list, render_one


def register_list_get(
    group: click.Group,
    *,
    list_fn: str,
    get_fn: str,
    default_columns: Sequence[str],
    filters: Sequence[FilterSpec],
    transform: Callable[[list[dict], AppContext], list[dict]] | None = None,
) -> None:
    filter_names = [f.name for f in filters]

    def _resolver_for(spec: FilterSpec) -> str | None:
        if spec.resolver:
            return spec.resolver

        if spec.name in NameResolver.FIELD_MAP:
            return NameResolver.FIELD_MAP[spec.name]

        if spec.name == "ids":
            return list_fn

        if spec.name.endswith("_ids"):
            singular = spec.name[:-1]

            if singular in NameResolver.FIELD_MAP:
                return NameResolver.FIELD_MAP[singular]

        return None

    resolver_for: dict[str, str | None] = {f.name: _resolver_for(f) for f in filters}

    for spec in filters:
        flag_basis = spec.name[:-3] if spec.name.endswith("_id") else spec.name
        is_plural = spec.name == "ids" or spec.name.endswith("_ids")

        if resolver_for[spec.name]:
            help_text = spec.help or (
                f"Filter by {flag_basis} "
                f"({'names or UUIDs (comma-separated)' if is_plural else 'name or UUID'})."
            )
        elif spec.name.endswith("_id"):
            help_text = spec.help or f"Filter by {flag_basis} (UUID)."
        elif is_plural:
            help_text = spec.help or f"Filter by {flag_basis} (comma-separated UUIDs)."
        else:
            help_text = spec.help or f"Filter by {spec.name}."

        group.params.append(
            click.Option(
                ["--" + flag_basis.replace("_", "-"), spec.name],
                default=None,
                type=bool if spec.type == "bool" else None,
                help=help_text,
            )
        )

    group.params.append(
        click.Option(
            ["--format", "fmt"],
            type=click.Choice(["table", "json", "csv"], case_sensitive=False),
            default="table",
            show_default=True,
            help="Output format.",
        )
    )
    group.params.append(
        click.Option(
            ["--query"],
            default=None,
            help="Comma-separated list of columns to display (overrides defaults).",
        )
    )

    @click.pass_context
    def list_callback(ctx: click.Context, **kwargs: Any) -> None:
        if ctx.invoked_subcommand is not None:
            return

        app: AppContext = ctx.obj
        filter_kwargs: dict[str, Any] = {}

        for n in filter_names:
            v = kwargs.get(n)
            if v is None:
                continue

            r = resolver_for[n]
            if r and isinstance(v, str) and v not in ("null", "notnull"):
                if n == "ids" or n.endswith("_ids"):
                    v = ",".join(
                        app.resolver.resolve(r, item.strip())
                        for item in v.split(",")
                        if item.strip()
                    )
                else:
                    v = app.resolver.resolve(r, v)
            filter_kwargs[n] = v

        items = getattr(app.client, list_fn)(**filter_kwargs)
        if transform is not None:
            items = transform(items, app)
        render_list(
            items,
            default_columns=default_columns,
            fmt=kwargs.pop("fmt", "table"),
            query=kwargs.pop("query", None),
            resolver=app.resolver,
        )

    group.callback = list_callback

    @group.command("__get__", hidden=True)
    @click.argument("name_or_id")
    @click.option(
        "--format",
        "fmt",
        type=click.Choice(["table", "json", "csv"], case_sensitive=False),
        default="table",
        show_default=True,
        help="Output format.",
    )
    @click.option(
        "--query",
        default=None,
        help="Comma-separated list of columns to display (overrides defaults).",
    )
    @click.pass_obj
    def get_cmd(app: AppContext, name_or_id: str, fmt: str, query: str | None) -> None:
        render_one(
            getattr(app.client, get_fn)(app.resolver.resolve(list_fn, name_or_id)),
            fmt=fmt,
            query=query,
            resolver=app.resolver,
        )


COMMON_FILTERS: list[FilterSpec] = [
    FilterSpec("ids", help="Comma-separated list of UUIDs."),
    FilterSpec("created_ge", help="Created at or after (ISO timestamp)."),
    FilterSpec("created_le", help="Created at or before (ISO timestamp)."),
    FilterSpec("zone_id", help="Restrict to a specific zone."),
    FilterSpec("name_ilike", help="Case-insensitive substring match on name."),
    FilterSpec("status", help="Filter by status."),
    FilterSpec("tags", help="JSON-encoded tag selector."),
]


def merged_filters(*sets: Sequence[FilterSpec]) -> list[FilterSpec]:
    seen: dict[str, FilterSpec] = {}
    for s in sets:
        for f in s:
            seen.setdefault(f.name, f)

    return list(seen.values())
