from __future__ import annotations

import click

from ...utils import StdoutHelpGroup, print_help_if_no_subcommand
from .nic import nic
from .public_ip import public_ip
from .subnet import subnet
from .vnet import vnet


@click.group("network", cls=StdoutHelpGroup, help="Network resources.")
@click.pass_context
def network(ctx: click.Context) -> None:
    print_help_if_no_subcommand(ctx)


network.add_command(vnet)
network.add_command(subnet)
network.add_command(nic)
network.add_command(public_ip)
