from __future__ import annotations

from typing import Any

import click


class ResourceGroup(click.Group):
    """Group that surfaces `list`/`get` as explicit subcommands.

    Bare `eci <noun>` shows help (modern CLI convention — kubectl, gcloud,
    gh, doctl, flyctl, az, vault all behave this way). Positional shorthand
    `eci <noun> <name>` is preserved as an alias for `eci <noun> get <name>`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("no_args_is_help", True)
        kwargs.setdefault("invoke_without_command", False)
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if args and args[0] in ("--help", "-h", "-help"):
            return super().parse_args(ctx, args)

        if args and not args[0].startswith("-") and args[0] not in self.commands:
            args = ["get", *args]
        return super().parse_args(ctx, args)
