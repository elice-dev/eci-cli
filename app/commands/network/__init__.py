from __future__ import annotations

import click

from .ip import ip
from .nic import nic
from .subnet import subnet
from .vnet import vnet
from .vpn import vpn


@click.group("network", help="Network resources.")
def network() -> None:
    pass


network.add_command(vnet)
network.add_command(subnet)
network.add_command(nic)
network.add_command(ip)
network.add_command(vpn)
