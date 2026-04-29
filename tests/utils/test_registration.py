from __future__ import annotations

from app.utils.options import FilterSpec
from app.utils.registration import COMMON_FILTERS, merged_filters


def test_merged_filters_dedupes_by_name():
    extra = [FilterSpec("status"), FilterSpec("vm_kind")]
    merged = merged_filters(COMMON_FILTERS, extra)
    names = [f.name for f in merged]
    assert names.count("status") == 1
    assert "vm_kind" in names


def test_merged_filters_first_occurrence_wins():
    a = [FilterSpec("status", help="from a")]
    b = [FilterSpec("status", help="from b")]
    merged = merged_filters(a, b)
    assert len(merged) == 1
    assert merged[0].help == "from a"
