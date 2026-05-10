from __future__ import annotations

import click

from ...utils import StdoutHelpGroup, print_help_if_no_subcommand
from .cluster import cluster
from .launch import vm_launch
from .ssh import vm_ssh
from .vm import vm


@click.group(
    "compute", cls=StdoutHelpGroup, help="Compute resources (VMs and clusters)."
)
@click.pass_context
def compute(ctx: click.Context) -> None:
    print_help_if_no_subcommand(ctx)


vm.add_command(vm_launch)

compute.add_command(vm)
compute.add_command(cluster)
compute.add_command(vm_ssh)
