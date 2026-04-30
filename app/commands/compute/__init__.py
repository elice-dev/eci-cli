from __future__ import annotations

import click

from .cluster import cluster
from .launch import vm_launch
from .ssh import vm_ssh
from .vm import vm


@click.group("compute", help="Compute resources (VMs and clusters).")
def compute() -> None:
    pass


vm.add_command(vm_launch)

compute.add_command(vm)
compute.add_command(cluster)
compute.add_command(vm_ssh)
