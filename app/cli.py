from __future__ import annotations

import sys

import click
import truststore

from . import __version__
from .client import ECIClient, ECIError
from .config import Config
from .utils import AppContext, NameResolver, StdoutHelpGroup, err_console
from .commands.compute import compute
from .commands.configure import config_group, configure
from .commands.image import image
from .commands.instance_type import instance_type
from .commands.network import network
from .commands.org import org
from .commands.pricing import pricing
from .commands.region import region
from .commands.storage import storage
from .commands.vm_spec import vm_spec
from .commands.zone import zone

truststore.inject_into_ssl()


class _RootGroup(StdoutHelpGroup):
    """Records the raw argv so the root callback can detect deep `-h/--help`."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        ctx.meta["eci.raw_args"] = list(args)
        return super().parse_args(ctx, args)


@click.group(
    cls=_RootGroup,
    help="ECI — Elice Cloud Infrastructure CLI.",
    context_settings={"help_option_names": ["-h", "--help", "-help"]},
)
@click.version_option(__version__, "-V", "--version", prog_name="eci")
@click.option(
    "--zone",
    "zone_override",
    default=None,
    help="Override configured zone (UUID or name).",
)
@click.pass_context
def cli(ctx: click.Context, zone_override: str | None) -> None:
    cfg = Config.load()

    if ctx.invoked_subcommand in {"configure", "config"}:
        ctx.obj = None
        return

    raw_args = ctx.meta.get("eci.raw_args", [])
    if any(a in ("--help", "-h") for a in raw_args):
        ctx.obj = None
        return

    if not cfg.api_token:
        err_console.print(
            "[red]error[/red]: api_token is not set. Run `eci configure`."
        )
        sys.exit(2)

    client = ECIClient(cfg)

    if zone_override:
        try:
            cfg.zone_id = NameResolver(client).resolve("list_zones", zone_override)
            client.config = cfg
        except (ECIError, click.ClickException) as e:
            err_console.print(f"[red]zone override failed[/red]: {e}")
            sys.exit(2)

    ctx.obj = AppContext(client=client)


cli.add_command(configure)
cli.add_command(config_group)

cli.add_command(region)
cli.add_command(zone)
cli.add_command(instance_type)
cli.add_command(image)
cli.add_command(pricing)
cli.add_command(org)

cli.add_command(compute)
cli.add_command(network)
cli.add_command(storage)

cli.add_command(vm_spec)


def main() -> None:
    try:
        cli.main(standalone_mode=False)
    except click.ClickException as e:
        e.show()
        sys.exit(e.exit_code)
    except click.exceptions.Abort:
        err_console.print("[yellow]aborted[/yellow]")
        sys.exit(130)
    except ECIError as e:
        err_console.print(f"[red]API error[/red]: {e}")
        sys.exit(2)
    except BrokenPipeError:
        sys.exit(0)
    except Exception as e:
        err_console.print(f"[red]error[/red]: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
