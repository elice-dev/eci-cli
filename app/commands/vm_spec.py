from __future__ import annotations

import click
import yaml

from ..config import Config
from .compute._pricing import PriceType


@click.group("vm-spec", help="Manage saved VM launch specs (vm_defaults).")
def vm_spec() -> None:
    pass


@vm_spec.command("list", help="List saved spec names.")
def vm_spec_list() -> None:
    cfg = Config.load()
    for name in (cfg.vm_defaults or {}).keys():
        click.echo(name)


@vm_spec.command("show", help="Print a saved spec.")
@click.argument("name")
def vm_spec_show(name: str) -> None:
    cfg = Config.load()
    spec = (cfg.vm_defaults or {}).get(name)
    if not spec:
        raise click.ClickException(f"no spec named {name!r}")
    click.echo(yaml.safe_dump(spec, sort_keys=False))


@vm_spec.command("save", help="Create or overwrite a VM launch spec.")
@click.argument("name")
@click.option(
    "--instance-type",
    "instance_type",
    default=None,
    help="Instance type name or UUID (e.g. 'M-8').",
)
@click.option(
    "--price-type",
    "price_type",
    type=click.Choice([t.value for t in PriceType]),
    default=None,
    help="Price type (default: ondemand at launch time).",
)
@click.option("--pricing-id", "pricing_id", default=None, help="Explicit pricing UUID.")
@click.option("--image", default=None, help="OS image name or UUID.")
@click.option("--size-gib", "size_gib", type=int, default=None)
@click.option("--subnet", default=None, help="Subnet name or UUID.")
@click.option("--username", default=None)
@click.option("--force/--no-force", default=False, help="Overwrite an existing spec.")
def vm_spec_save(
    name: str,
    instance_type: str | None,
    price_type: str | None,
    pricing_id: str | None,
    image: str | None,
    size_gib: int | None,
    subnet: str | None,
    username: str | None,
    force: bool,
) -> None:
    cfg = Config.load()
    cfg.vm_defaults = cfg.vm_defaults or {}
    if name in cfg.vm_defaults and not force:
        raise click.ClickException(
            f"spec {name!r} already exists; use --force to overwrite"
        )
    spec = {
        k: v
        for k, v in {
            "instance_type": instance_type,
            "price_type": price_type,
            "pricing_id": pricing_id,
            "image": image,
            "size_gib": size_gib,
            "subnet": subnet,
            "username": username,
        }.items()
        if v is not None
    }
    if not spec:
        raise click.ClickException(
            "at least one of --instance-type/--price-type/--pricing-id/"
            "--image/--size-gib/--subnet/--username is required"
        )
    cfg.vm_defaults[name] = spec
    cfg.save()
    click.echo(f"saved vm_defaults.{name}")


@vm_spec.command("delete", help="Delete a saved spec.")
@click.argument("name")
def vm_spec_delete(name: str) -> None:
    cfg = Config.load()
    if name not in (cfg.vm_defaults or {}):
        raise click.ClickException(f"no spec named {name!r}")
    del cfg.vm_defaults[name]
    cfg.save()
    click.echo(f"deleted vm_defaults.{name}")
