from __future__ import annotations

import click
import yaml

from ..client import ECIClient, ECIError
from ..config import CONFIG_PATH, Config
from ..utils import (
    NameResolver,
    StdoutHelpGroup,
    err_console,
    print_help_if_no_subcommand,
)
from ..utils.name_resolver import is_uuid

ENDPOINT_MINGAN = "https://portal.elice.cloud/api"
ENDPOINT_GOV = "https://portal.gov.elice.cloud/api"


def _prompt_endpoint(current: str) -> str:
    default = "2" if current == ENDPOINT_GOV else "1"
    click.echo("api_endpoint:")
    click.echo(
        f"  1) 민간용 ({ENDPOINT_MINGAN})" + ("  (default)" if default == "1" else "")
    )
    click.echo(
        f"  2) 공공기관용 ({ENDPOINT_GOV})" + ("  (default)" if default == "2" else "")
    )
    choice = click.prompt(
        "choice",
        type=click.Choice(["1", "2"]),
        default=default,
        show_choices=False,
        show_default=False,
    )
    return ENDPOINT_MINGAN if choice == "1" else ENDPOINT_GOV


def _auto_pick_zone(cfg: Config) -> str | None:
    """Return a zone id from the API: silent for one zone, prompt for many."""
    try:
        zones = ECIClient(cfg).list_zones()
    except ECIError as e:
        err_console.print(f"[yellow]warning[/yellow]: could not list zones: {e}")
        return None
    if not zones:
        err_console.print("[yellow]warning[/yellow]: no zones available")
        return None
    if len(zones) == 1:
        z = zones[0]
        click.echo(f"zone: {z.get('name')} (auto-selected, only zone available)")
        return z["id"]
    click.echo("zone:")
    for i, z in enumerate(zones, 1):
        suffix = "  (default)" if i == 1 else ""
        click.echo(f"  {i}) {z.get('name')}{suffix}")
    choice = click.prompt(
        "choice",
        type=click.Choice([str(i) for i in range(1, len(zones) + 1)]),
        default="1",
        show_choices=False,
        show_default=False,
    )
    return zones[int(choice) - 1]["id"]


@click.group("config", cls=StdoutHelpGroup, help="Inspect/edit the local config file.")
@click.pass_context
def config_group(ctx: click.Context) -> None:
    print_help_if_no_subcommand(ctx)


@config_group.command(
    "init",
    help=(
        "First-time setup of ~/.eci/config.yaml.\n"
        "\n"
        "Prompts for endpoint (1: 민간용 / 2: 공공기관용) and token, then\n"
        "auto-selects the zone (single zone → silent; multiple → prompt).\n"
        "\n"
        "\b\n"
        "Endpoints:\n"
        f"  민간용 (default): {ENDPOINT_MINGAN}\n"
        f"  공공기관용       : {ENDPOINT_GOV}\n"
        "\n"
        "Get a token at: Elice Cloud portal → 사용자 관리 →\n"
        "사용자 액세스 토큰 → 토큰 생성\n"
        "\n"
        "For non-interactive setup, use `eci config set` to write each\n"
        "field directly.\n"
    ),
)
def config_init() -> None:
    cfg = Config.load()
    cfg.api_endpoint = _prompt_endpoint(cfg.api_endpoint)
    cfg.api_token = click.prompt(
        "api_token",
        default=cfg.api_token or "",
        hide_input=True,
        show_default=False,
    )
    if not cfg.api_token:
        raise click.ClickException("api_token is required")

    picked = _auto_pick_zone(cfg)
    if picked:
        cfg.zone_id = picked

    cfg.save()
    click.echo(f"saved {CONFIG_PATH}")


@config_group.command(
    "set",
    help=(
        "Set a config value. Values are stored as strings; use `vm-spec save` "
        "for typed VM defaults.\n"
        "\n"
        "\b\n"
        "Valid paths:\n"
        "  api_endpoint, api_token, zone_id\n"
        "  vm_defaults.<spec>.<field>\n"
        "\n"
        "\b\n"
        "Full non-interactive setup:\n"
        "  eci config set api_endpoint https://portal.elice.cloud/api\n"
        "  eci config set api_token <TOKEN>\n"
        "  eci config set zone_id auto          # single-zone org → resolved\n"
        "                                       # multi-zone org → error w/ list\n"
        "  eci config verify\n"
        "\n"
        "\b\n"
        "Get a token at: Elice Cloud portal → 사용자 관리 →\n"
        "사용자 액세스 토큰 → 토큰 생성\n"
        "\n"
        "\b\n"
        "Update a single field:\n"
        "  eci config set api_token <NEW_TOKEN>\n"
        "  eci config set zone_id central-01-a\n"
    ),
)
@click.argument("path")
@click.argument("value")
def config_set(path: str, value: str) -> None:
    cfg = Config.load()

    if path == "zone_id" and value == "auto":
        value = _resolve_zone_auto(cfg)

    try:
        cfg.set_path(path, value)
    except KeyError as e:
        raise click.ClickException(str(e).strip("'"))

    cfg.save()
    click.echo(f"set {path}" + (f" = {value}" if path == "zone_id" else ""))


def _resolve_zone_auto(cfg: Config) -> str:
    """Resolve zone_id=auto: return single zone's id, or error with candidate list."""
    if not cfg.api_token:
        raise click.ClickException(
            "zone_id=auto needs api_token set first. "
            "Run: eci config set api_token <TOKEN>"
        )

    try:
        zones = ECIClient(cfg).list_zones()
    except ECIError as e:
        raise click.ClickException(f"could not list zones: {e}") from None

    if not zones:
        raise click.ClickException("no zones available for this token")

    if len(zones) == 1:
        return zones[0]["id"]

    names = "\n".join(f"  {z.get('name')}" for z in zones)
    raise click.ClickException(
        f"multiple zones available; pick one:\n{names}\n"
        "Run: eci config set zone_id <NAME>"
    )


@config_group.command("show", help="Print the current config (yaml).")
def config_show() -> None:
    cfg = Config.load()
    if CONFIG_PATH.exists():
        click.echo(f"# config file: {CONFIG_PATH}")
    else:
        click.echo(f"# config file: {CONFIG_PATH} (not found — showing defaults)")
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
            if field == "api_token":
                click.echo(
                    "    hint: eci config set api_token <TOKEN>\n"
                    "          (portal.elice.cloud → 사용자 관리 → 사용자 액세스 토큰)",
                    err=True,
                )
            elif field == "zone_id":
                click.echo("    hint: eci config set zone_id auto", err=True)

    if failures:
        if any("not set" in f for f in failures):
            click.echo(
                "\nFull setup:\n"
                "  eci config set api_token <TOKEN>\n"
                "  eci config set zone_id auto\n"
                "  eci config verify",
                err=True,
            )
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
