from __future__ import annotations

import click

from .block import block
from .object import object_storage
from .pfs import pfs


@click.group("storage", help="Storage resources.")
def storage() -> None:
    pass


storage.add_command(block)
storage.add_command(object_storage)
storage.add_command(pfs)
