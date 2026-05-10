from __future__ import annotations

from typing import Any

import click


class StdoutHelpGroup(click.Group):
    """A Click group that prints help on stdout (exit 0) when called with no subcommand.

    Click's default sends `Usage: ...` to stderr with exit 2 — treating empty
    invocation as an error. AWS CLI / gcloud / kubectl all return help on stdout.

    Pair this with a callback that checks `ctx.invoked_subcommand is None` and
    calls `click.echo(ctx.get_help()); ctx.exit(0)` (see `print_help_if_no_subcommand`).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("no_args_is_help", False)
        kwargs.setdefault("invoke_without_command", True)
        super().__init__(*args, **kwargs)


def print_help_if_no_subcommand(ctx: click.Context) -> None:
    """Print help on stdout and exit 0 when a group is invoked without a subcommand.

    Call this at the top of a `StdoutHelpGroup` callback.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)
