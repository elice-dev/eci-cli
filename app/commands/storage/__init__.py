from __future__ import annotations

import click

from ...utils import StdoutHelpGroup, print_help_if_no_subcommand
from .block import block
from .object import object_storage
from .pfs import pfs


@click.group("storage", cls=StdoutHelpGroup, help="Storage resources.")
@click.pass_context
def storage(ctx: click.Context) -> None:
    print_help_if_no_subcommand(ctx)


storage.add_command(block)
storage.add_command(object_storage)
storage.add_command(pfs)
