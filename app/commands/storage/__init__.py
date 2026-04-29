from __future__ import annotations

import click

from .block import block
from .object import obj
from .pfs import pfs


@click.group("storage", help="Storage resources.")
def storage() -> None:
    pass


storage.add_command(block)
storage.add_command(obj)
storage.add_command(pfs)
