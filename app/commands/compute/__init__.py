from __future__ import annotations

import click

from ...utils import StdoutHelpGroup
from .cluster import cluster
from .launch import vm_launch
from .ssh import vm_ssh
from .vm import vm


@click.group(
    "compute", cls=StdoutHelpGroup, help="Compute resources (VMs and clusters)."
)
def compute() -> None:
    pass


vm.add_command(vm_launch)

compute.add_command(vm)
compute.add_command(cluster)
compute.add_command(vm_ssh)
