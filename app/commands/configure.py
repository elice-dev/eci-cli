from __future__ import annotations

import click
import yaml

from ..client import ECIClient, ECIError
from ..config import CONFIG_PATH, Config
from ..utils import NameResolver
from ..utils.name_resolver import is_uuid


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


@config_group.command(
    "set",
    help=(
        "Set a config value (dotted path). Values are stored as strings; "
        "use `vm-spec save` for typed VM defaults."
    ),
)
@click.argument("path")
@click.argument("value")
def config_set(path: str, value: str) -> None:
    cfg = Config.load()

    try:
        cfg.set_path(path, value)
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


@config_group.command(
    "verify",
    help="Check that the current config can authenticate and resolve saved references.",
)
def config_verify() -> None:
    cfg = Config.load()
    failures: list[str] = []

    for field in ("api_endpoint", "api_token", "zone_id"):
        if not getattr(cfg, field):
            failures.append(f"{field}: not set")
            click.echo(f"  ✗ {field}: not set", err=True)

    if failures:
        raise click.ClickException("required config fields missing")

    client = ECIClient(cfg)
    resolver = NameResolver(client)

    try:
        org = client.organization()
        click.echo(f"  ✓ auth: org={org.get('name', '?')}")
    except ECIError as e:
        click.echo(f"  ✗ auth: {e}", err=True)
        raise click.ClickException("authentication failed") from None

    try:
        if is_uuid(cfg.zone_id):
            zones = client.list_zones()
            match = next((z for z in zones if z["id"] == cfg.zone_id), None)
            if match is None:
                failures.append(f"zone_id={cfg.zone_id} not found")
                click.echo(f"  ✗ zone_id: {cfg.zone_id} not found", err=True)
            else:
                click.echo(f"  ✓ zone: {match.get('name')}")
        else:
            zid = resolver.resolve("list_zones", cfg.zone_id)
            click.echo(f"  ✓ zone: {cfg.zone_id} → {zid}")
    except (ECIError, click.ClickException) as e:
        failures.append(f"zone_id: {e}")
        click.echo(f"  ✗ zone_id: {e}", err=True)

    fields_to_check: tuple[tuple[str, str], ...] = (
        ("pricing", "list_pricings"),
        ("image", "list_images"),
        ("subnet", "list_subnets"),
    )
    for spec_name, spec in (cfg.vm_defaults or {}).items():
        spec_failures: list[str] = []
        if not isinstance(spec, dict):
            click.echo(f"  ✗ vm_defaults.{spec_name}: not a mapping", err=True)
            failures.append(f"vm_defaults.{spec_name}: not a mapping")
            continue
        for field, list_fn in fields_to_check:
            value = spec.get(field)
            if value is None or value == "":
                continue
            if not isinstance(value, str):
                spec_failures.append(
                    f"{field}={value!r}: must be a string (got {type(value).__name__})"
                )
                continue
            try:
                resolver.resolve(list_fn, value)
            except (ECIError, click.ClickException) as e:
                spec_failures.append(f"{field}={value!r}: {e}")
        size_gib = spec.get("size_gib")
        if size_gib is not None and not isinstance(size_gib, int):
            spec_failures.append(
                f"size_gib={size_gib!r}: must be an int (got {type(size_gib).__name__})"
            )
        if spec_failures:
            click.echo(f"  ✗ vm_defaults.{spec_name}:", err=True)
            for line in spec_failures:
                click.echo(f"      {line}", err=True)
                failures.append(f"vm_defaults.{spec_name}.{line}")
        else:
            click.echo(f"  ✓ vm_defaults.{spec_name}")

    if failures:
        raise click.ClickException(f"{len(failures)} check(s) failed")
    click.echo("all checks passed")
