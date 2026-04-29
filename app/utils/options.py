from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import click


def output_options(fn: Callable) -> Callable:
    fn = click.option(
        "--format",
        "fmt",
        type=click.Choice(["table", "json", "csv"], case_sensitive=False),
        default="table",
        show_default=True,
        help="Output format.",
    )(fn)
    fn = click.option(
        "--query",
        default=None,
        help="Comma-separated list of columns to display (overrides defaults).",
    )(fn)
    
    return fn


@dataclass
class FilterSpec:
    name: str
    type: str = "string"  # "string" | "bool"
    help: str = ""
    resolver: str | None = None


def filter_options(specs: Sequence[FilterSpec]) -> Callable:
    def decorator(fn: Callable) -> Callable:
        for s in reversed(list(specs)):
            fn = click.option(
                "--" + s.name.replace("_", "-"),
                s.name,
                default=None,
                type=bool if s.type == "bool" else None,
                help=s.help or f"Filter by {s.name}.",
            )(fn)
        return fn

    return decorator
