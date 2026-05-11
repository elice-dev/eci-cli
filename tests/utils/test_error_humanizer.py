"""Tests for the F6 error-humanizer layer."""

from __future__ import annotations

import pytest

from app.client import ECIError
from app.utils.error_humanizer import (
    HumanizedError,
    format_humanized,
    humanize_eci_error,
)


@pytest.fixture(autouse=True)
def _stub_lookups(monkeypatch):
    """Patch the API-touching helpers so humanize runs offline."""
    from app.utils import error_humanizer

    name_table = {
        ("instance_type", "uuid-c2"): "C-2",
        ("instance_type", "uuid-c4"): "C-4",
        ("instance_type", "uuid-m2"): "M-2",
    }

    def fake_name(kind, uuid):
        return name_table.get((kind, uuid))

    def fake_alts(kind, uuid):
        if kind != "instance_type":
            return []
        return [
            f"{name} (used {used})"
            for (k, uid), name in name_table.items()
            if k == kind and uid != uuid
            for used in [{"uuid-c2": 5, "uuid-c4": 1, "uuid-m2": 1}.get(uid, 0)]
        ]

    monkeypatch.setattr(error_humanizer, "_try_lookup_name", fake_name)
    monkeypatch.setattr(error_humanizer, "_try_alternatives", fake_alts)


def test_quota_error_resolves_uuid_to_name():
    err = ECIError(
        409,
        "resource_quota_exceed",
        "quota exceeded",
        detail={"resource": "instance_type.uuid-c2", "used": 5, "limit": 5},
    )
    h = humanize_eci_error(err)
    assert h is not None
    assert h.title == "Resource quota exceeded"
    assert any("instance_type 'C-2'" in line for line in h.lines)
    assert any("uuid-c2" in line for line in h.lines)
    assert any("used 5 / limit 5" in line for line in h.lines)


def test_quota_error_includes_alternatives():
    err = ECIError(
        409,
        "resource_quota_exceed",
        "quota exceeded",
        detail={"resource": "instance_type.uuid-c2", "used": 5, "limit": 5},
    )
    h = humanize_eci_error(err)
    assert h is not None
    assert h.hint is not None
    assert "C-4" in h.hint
    assert "M-2" in h.hint
    assert "C-2" not in h.hint  # the maxed-out resource should be excluded


def test_quota_error_unknown_uuid_still_renders_uuid():
    err = ECIError(
        409,
        "resource_quota_exceed",
        "quota exceeded",
        detail={"resource": "instance_type.uuid-unknown", "used": 1, "limit": 1},
    )
    h = humanize_eci_error(err)
    assert h is not None
    assert any("uuid-unknown" in line for line in h.lines)


def test_non_quota_error_with_resource_uuid_swaps_name():
    err = ECIError(
        400,
        "invalid_argument",
        "bad request",
        detail={"resource": "instance_type.uuid-c4"},
    )
    h = humanize_eci_error(err)
    assert h is not None
    assert any("C-4" in line for line in h.lines)


def test_error_without_detail_resource_returns_none():
    err = ECIError(500, None, "boom")
    assert humanize_eci_error(err) is None


def test_format_humanized_emits_title_lines_and_hint():
    h = HumanizedError(
        title="Quota exceeded",
        lines=["Resource: instance_type 'C-2'", "Quota: 5/5"],
        hint="Try C-4 instead",
    )
    s = format_humanized(h)
    assert "Quota exceeded" in s
    assert "  Resource: instance_type 'C-2'" in s
    assert "Hint: Try C-4 instead" in s


def test_org_wide_public_ip_quota_emits_kind_specific_hint():
    """public_ip quota has no per-resource UUID (it caps a kind).
    Humanizer should still produce a structured message with a hint
    pointing to `--no-public-ip` and `ip delete`."""
    err = ECIError(
        409,
        "resource_quota_exceed",
        "public IP quota exceeded",
        detail={"resource": "public_ip", "used": 10, "limit": 10},
    )
    h = humanize_eci_error(err)
    assert h is not None
    assert h.title == "Resource quota exceeded"
    assert any("public_ip" in line for line in h.lines)
    assert any("used 10 / limit 10" in line for line in h.lines)
    assert h.hint is not None
    assert "--no-public-ip" in h.hint
    assert "ip delete" in h.hint


def test_org_wide_virtual_network_quota_emits_kind_specific_hint():
    err = ECIError(
        409,
        "resource_quota_exceed",
        "vnet quota exceeded",
        detail={"resource": "virtual_network", "used": 10, "limit": 10},
    )
    h = humanize_eci_error(err)
    assert h is not None
    assert h.hint is not None
    assert "vnet delete" in h.hint
