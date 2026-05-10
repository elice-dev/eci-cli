from __future__ import annotations

from typing import Any

import click


class StdoutHelpGroup(click.Group):
    """A Click group that prints help on stdout (exit 0) when called with no subcommand.

    Click's default sends `Usage: ...` to stderr with exit 2 — treating empty
    invocation as an error. AWS CLI / gcloud / kubectl all return help on stdout.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("no_args_is_help", False)
        kwargs.setdefault("invoke_without_command", True)
        super().__init__(*args, **kwargs)

    def invoke(self, ctx: click.Context) -> Any:
        if ctx.invoked_subcommand is None and not ctx.protected_args:
            click.echo(ctx.get_help())
            ctx.exit(0)
        return super().invoke(ctx)
