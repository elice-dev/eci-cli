from __future__ import annotations

from collections import Counter

import click

from ..utils import AppContext, FilterSpec, ResourceGroup, register_list_get


@click.group("instance-type", cls=ResourceGroup, help="List/get instance types.")
def instance_type() -> None:
    pass


_CATEGORY_ORDER = {"C": 0, "M": 1, "G": 2, "N": 3}


def _sort_by_category(items: list[dict], app: AppContext) -> list[dict]:
    """Sort by name-prefix category (C → M → G → N), then by cpu_vcore.

    Backend returns instance types in roughly created_at order, which is
    noisy for users. `C-` (CPU optimized) and `M-` (memory optimized) are
    accelerator-free; `G-` (GPU) and `N-` (NPU) are accelerator-backed.
    Group by that mental model first, then size within the group.
    """

    def key(it: dict) -> tuple[int, int, str]:
        name = it.get("name") or ""
        prefix = name.split("-", 1)[0] if name else ""
        return (
            _CATEGORY_ORDER.get(prefix, 99),
            it.get("cpu_vcore") or 0,
            name,
        )

    return sorted(items, key=key)


def _summarize_devices(items: list[dict], app: AppContext) -> list[dict]:
    """Render the `devices` accelerator list as a compact summary for display.

    Backend stores `devices: list[DeviceKindEnum]` — accelerators only
    (NVIDIA GPUs, Furiosa/Rebellions NPUs); CPU instances have an empty list.

    Table/CSV get a readable string ("cpu only", "2x nvidia_h100_80gb_sxm",
    "1x a + 2x b" for mixed). JSON keeps the raw list so scripts piping
    `eci instance-type --format json | jq .devices` are unaffected.
    """
    out: list[dict] = []
    for it in items:
        copy = dict(it)
        devs = copy.get("devices")
        if not devs:
            copy["devices"] = "cpu only"
        elif isinstance(devs, list):
            counts = Counter(devs)
            copy["devices"] = " + ".join(
                f"{n}x {kind}" for kind, n in counts.most_common()
            )
        out.append(copy)
    return out


register_list_get(
    instance_type,
    list_fn="list_instance_types",
    get_fn="get_instance_type",
    default_columns=("name", "cpu_vcore", "memory_gib", "devices"),
    filters=[
        FilterSpec("ids"),
        FilterSpec("created_ge"),
        FilterSpec("created_le"),
        FilterSpec("organization_id"),
        FilterSpec("zone_id"),
        FilterSpec("name_ilike"),
        FilterSpec("activated", type="bool"),
    ],
    transform=_sort_by_category,
    display_transform=_summarize_devices,
    column_labels={"devices": "accelerators"},
)
