from __future__ import annotations

import click

from ..utils import (
    AppContext,
    StdoutHelpGroup,
    emit_action_result,
    output_options,
    print_help_if_no_subcommand,
    render_one,
)


@click.group("org", cls=StdoutHelpGroup, help="Organization info.")
@click.pass_context
def org(ctx: click.Context) -> None:
    print_help_if_no_subcommand(ctx)


@org.command("info", help="Show organization info.")
@output_options
@click.pass_obj
def org_info(app: AppContext, fmt: str, query: str | None) -> None:
    render_one(app.client.organization(), fmt=fmt, query=query, resolver=app.resolver)


@org.command("usage", help="Show organization-wide resource usage.")
@output_options
@click.pass_obj
def org_usage(app: AppContext, fmt: str, query: str | None) -> None:
    item = app.client.organization_resource_usage()
    if fmt == "json":
        emit_action_result(item)
    else:
        render_one(item, fmt=fmt, query=query, resolver=app.resolver)
