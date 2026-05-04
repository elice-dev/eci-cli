from __future__ import annotations

import enum

import click

from ...client import PricingResourceKind
from ...utils import AppContext
from ...utils.name_resolver import is_uuid


class PriceType(enum.StrEnum):
    ondemand = enum.auto()
    reserved = enum.auto()
    spot = enum.auto()


def resolve_create_pricing(
    app: AppContext,
    *,
    instance_type: str | None,
    price_type: str | None,
    pricing_id: str | None,
) -> tuple[str, str]:
    if not instance_type and not pricing_id:
        raise click.ClickException("either --instance-type or --pricing-id is required")

    effective_pt = price_type or PriceType.ondemand.value

    it_id: str | None = None
    if instance_type:
        it_id = app.resolver.resolve("list_instance_types", instance_type)

    if pricing_id:
        if not is_uuid(pricing_id):
            raise click.ClickException("--pricing-id must be a UUID")
        pricing = app.client.get_pricing(pricing_id)
        if pricing.get("resource_kind") != PricingResourceKind.vm_allocation:
            raise click.ClickException(
                f"--pricing-id is not a VM pricing "
                f"(resource_kind={pricing.get('resource_kind')!r})"
            )
        if it_id and pricing.get("resource_id") != it_id:
            raise click.ClickException(
                f"--pricing-id and --instance-type mismatch: "
                f"pricing.resource_id={pricing.get('resource_id')!r} != {it_id!r}"
            )
        if (instance_type or price_type) and pricing.get(
            "pricing_type"
        ) != effective_pt:
            raise click.ClickException(
                f"--pricing-id and --price-type mismatch: "
                f"pricing.pricing_type={pricing.get('pricing_type')!r} != {effective_pt!r}"
            )
        return pricing["id"], pricing["resource_id"]

    assert it_id is not None
    pricings = app.client.list_pricings(
        resource_kind=PricingResourceKind.vm_allocation,
        resource_id=it_id,
        pricing_type=effective_pt,
        activated=True,
    )
    if not pricings:
        raise click.ClickException(
            f"no {effective_pt} pricing for instance type {instance_type!r}"
        )
    if len(pricings) > 1:
        candidates = "\n  ".join(p["id"] for p in pricings)
        raise click.ClickException(
            f"multiple {effective_pt} pricings for instance type {instance_type!r}; "
            f"pass --pricing-id with one of:\n  {candidates}"
        )
    return pricings[0]["id"], it_id
