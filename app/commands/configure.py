from __future__ import annotations

import click
import yaml

from ..config import CONFIG_PATH, Config


@click.command("configure", help="Interactively configure ~/.eci/config.yaml.")
def configure() -> None:
    cfg = Config.load()
    cfg.api_endpoint = click.prompt("api_endpoint", default=cfg.api_endpoint)
    cfg.api_token = click.prompt(
        "api_token",
        default=cfg.api_token or "",
        hide_input=True,
        show_default=False,
    )
    cfg.zone_id = click.prompt("zone_id", default=cfg.zone_id or "")
    cfg.save()
    click.echo(f"saved {CONFIG_PATH}")


@click.group("config", help="Inspect/edit the local config file.")
def config_group() -> None:
    pass


@config_group.command("set", help="Set a config value (dotted path).")
@click.argument("path")
@click.argument("value")
def config_set(path: str, value: str) -> None:
    cfg = Config.load()
    parsed: object = value

    if value.isdigit():
        parsed = int(value)
    elif value.lower() in ("true", "false"):
        parsed = value.lower() == "true"

    try:
        cfg.set_path(path, parsed)
    except KeyError as e:
        raise click.ClickException(str(e).strip("'"))

    cfg.save()
    click.echo(f"set {path}")


@config_group.command("show", help="Print the current config (yaml).")
def config_show() -> None:
    cfg = Config.load()
    click.echo(
        yaml.safe_dump(
            {
                "api_endpoint": cfg.api_endpoint,
                "api_token": "***" if cfg.api_token else "",
                "zone_id": cfg.zone_id,
                "vm_defaults": cfg.vm_defaults,
            },
            sort_keys=False,
        )
    )


@config_group.command("list-vm-specs", help="List saved vm_defaults specs.")
def config_list_vm_specs() -> None:
    cfg = Config.load()
    for name in (cfg.vm_defaults or {}).keys():
        click.echo(name)


@config_group.command("show-vm-spec", help="Show one saved vm_defaults spec.")
@click.argument("name")
def config_show_vm_spec(name: str) -> None:
    cfg = Config.load()
    spec = (cfg.vm_defaults or {}).get(name)

    if not spec:
        raise click.ClickException(f"no spec named {name!r}")
    click.echo(yaml.safe_dump(spec, sort_keys=False))


@config_group.command("delete-vm-spec", help="Delete a saved vm_defaults spec.")
@click.argument("name")
def config_delete_vm_spec(name: str) -> None:
    cfg = Config.load()

    if name not in (cfg.vm_defaults or {}):
        raise click.ClickException(f"no spec named {name!r}")

    del cfg.vm_defaults[name]

    cfg.save()
    click.echo(f"deleted vm_defaults.{name}")
