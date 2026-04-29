from __future__ import annotations

from typing import Any

import click


class ResourceGroup(click.Group):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("no_args_is_help", False)
        kwargs.setdefault("invoke_without_command", True)
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if args and args[0] in ("--help", "-h"):
            return super().parse_args(ctx, args)

        if args and not args[0].startswith("-") and args[0] not in self.commands:
            args = ["__get__", *args]
        return super().parse_args(ctx, args)
