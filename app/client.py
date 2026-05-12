from __future__ import annotations

import enum
import json
import time
import uuid
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Config

PAGE_SIZE = 100


class VMAllocationStatus(enum.StrEnum):
    """Mirror of ResourceVirtualMachineAllocationStatusEnum on the API side."""

    queued = enum.auto()
    assigned = enum.auto()
    taken = enum.auto()
    started = enum.auto()
    terminating = enum.auto()
    terminated = enum.auto()

    @property
    def is_active(self) -> bool:
        return self in {
            VMAllocationStatus.assigned,
            VMAllocationStatus.taken,
            VMAllocationStatus.started,
            VMAllocationStatus.terminating,
        }


class VMStatus(enum.StrEnum):
    idle = enum.auto()
    allocated = enum.auto()
    deleted = enum.auto()


class BlockStorageStatus(enum.StrEnum):
    queued = enum.auto()
    assigned = enum.auto()
    prepared = enum.auto()
    deleting = enum.auto()
    deleted = enum.auto()


class PricingResourceKind(enum.StrEnum):
    vm_allocation = enum.auto()
    block_storage = enum.auto()
    block_storage_dr = enum.auto()
    object_storage = enum.auto()
    parallel_file_system = enum.auto()
    public_ip = enum.auto()


def is_active_allocation(allocation: dict) -> bool:
    raw = allocation.get("status")
    if not isinstance(raw, str):
        return False
    try:
        return VMAllocationStatus(raw).is_active
    except ValueError:
        return False


def _ilike(s: str) -> str:
    return s if "%" in s else f"%{s}%"


def _coerce_filter(key: str, value: Any) -> Any:
    if key == "name_ilike" and isinstance(value, str):
        return _ilike(value)

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (dict, list)):
        return json.dumps(value)

    return value


class ECIError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str, detail: Any = None):
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(
            f"[{status}{' ' + code if code else ''}] {message}"
            + (f" detail={json.dumps(detail, ensure_ascii=False)}" if detail else "")
        )


class ECIClient:
    def __init__(self, config: Config):
        self.config = config
        parsed = urlparse(config.api_endpoint)
        self.base = f"{parsed.scheme}://{parsed.netloc}"
        self.path_prefix = parsed.path.rstrip("/") or ""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.api_token}",
                "Content-Type": "application/json",
            }
        )

        # Only retry idempotent verbs by default. Auto-retrying POST/PATCH on
        # 502/504 risks creating duplicate resources when the server processed
        # the first request but the response was lost in transit (e.g. a
        # transient gateway timeout during `vm launch` → two VMs created).
        # We still send an Idempotency-Key header on each POST/PATCH (see
        # `post`/`patch` below) so the server *could* dedupe; until that's
        # in place, refusing to retry is the safer default.
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS", "PUT", "DELETE"]),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _url(self, path: str) -> str:
        return f"{self.base}{self.path_prefix}{path}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self.session.request(method, self._url(path), timeout=30, **kwargs)
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"message": resp.text}
            raise ECIError(
                resp.status_code,
                body.get("code"),
                body.get("message") or resp.text,
                body.get("detail"),
            )

        if resp.status_code == 204 or not resp.content:
            return None

        return resp.json()

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict) -> Any:
        # Idempotency-Key lets the server deduplicate retried writes. We
        # don't auto-retry POSTs ourselves, but operators (proxies, scripts
        # using `requests` Sessions, etc.) might.
        return self._request(
            "POST",
            path,
            json=body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

    def patch(self, path: str, body: dict) -> Any:
        return self._request(
            "PATCH",
            path,
            json=body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def _paginate(self, path: str, params: dict | None = None) -> list[dict]:
        params = dict(params or {})
        out: list[dict] = []
        skip = 0
        while True:
            params["skip"] = skip
            params["count"] = PAGE_SIZE
            page = self.get(path, params=params) or []
            out.extend(page)
            if len(page) < PAGE_SIZE:
                return out
            skip += PAGE_SIZE

    def _filters(self, *, include_zone: bool = True, **kwargs) -> dict:
        params: dict = {}
        if include_zone and kwargs.get("zone_id") is None and self.config.zone_id:
            params["filter_zone_id"] = self.zone_id

        for k, v in kwargs.items():
            if v is None:
                continue
            params[f"filter_{k}"] = _coerce_filter(k, v)

        return params

    @property
    def zone_id(self) -> str:
        if not self.config.zone_id:
            raise RuntimeError("zone_id is not configured. Run `eci configure`.")

        return self.config.zone_id

    def _scope(self) -> dict:
        return {"zone_id": self.zone_id}

    def organization(self) -> dict:
        return self.get("/user/organization")

    def organization_resource_usage(self) -> dict:
        return self.get("/user/organization/resource_usage")

    def list_regions(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/region", self._filters(include_zone=False, **filters)
        )

    def get_region(self, region_id: str) -> dict:
        return self.get(f"/user/region/{region_id}")

    def list_zones(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/infra/zone", self._filters(include_zone=False, **filters)
        )

    def get_zone(self, zone_id: str) -> dict:
        return self.get(f"/user/infra/zone/{zone_id}")

    def list_instance_types(self, **filters) -> list[dict]:
        return self._paginate("/user/infra/instance_type", self._filters(**filters))

    def get_instance_type(self, instance_type_id: str) -> dict:
        return self.get(f"/user/infra/instance_type/{instance_type_id}")

    def list_images(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/infra/block_storage_image", self._filters(**filters)
        )

    def get_image(self, image_id: str) -> dict:
        return self.get(f"/user/infra/block_storage_image/{image_id}")

    def list_pricings(self, **filters) -> list[dict]:
        return self._paginate("/user/pricing", self._filters(**filters))

    def get_pricing(self, pricing_id: str) -> dict:
        return self.get(f"/user/pricing/{pricing_id}")

    def find_pricing(
        self,
        name: str,
        pricing_type: str = "ondemand",
        resource_kind: str | None = None,
    ) -> dict:
        exact = [
            p
            for p in self.list_pricings(
                name_ilike=name,
                pricing_type=pricing_type,
                resource_kind=resource_kind,
                activated=True,
            )
            if p.get("name") == name
        ]

        if not exact:
            raise ECIError(
                404,
                None,
                f"pricing not found: name={name!r} type={pricing_type!r} kind={resource_kind!r}",
            )

        return exact[0]

    def list_vms(self, **filters) -> list[dict]:
        vms = self._paginate(
            "/user/resource/compute/virtual_machine", self._filters(**filters)
        )
        self._patch_allocated_status(vms)
        return vms

    def get_vm(self, vm_id: str) -> dict:
        vm = self.get(f"/user/resource/compute/virtual_machine/{vm_id}")
        if vm.get("status") == "allocated":
            for a in self.list_allocations(machine_id=vm_id):
                if is_active_allocation(a):
                    vm["status"] = a["status"]
                    break
        return vm

    def _patch_allocated_status(self, vms: list[dict]) -> None:
        if not any(vm.get("status") == "allocated" for vm in vms):
            return

        active: dict[str, str] = {}
        for a in self.list_allocations():
            if not is_active_allocation(a):
                continue
            mid = a.get("machine_id")
            if mid and mid not in active:
                active[mid] = a["status"]

        for vm in vms:
            if vm.get("status") == "allocated":
                new_status = active.get(vm["id"])
                if new_status:
                    vm["status"] = new_status

    def create_vm(
        self,
        *,
        name: str,
        instance_type_id: str,
        pricing_id: str,
        username: str,
        password: str,
        on_init_script: str = "",
        always_on: bool = False,
        dr: bool = False,
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/compute/virtual_machine",
            {
                **self._scope(),
                "name": name,
                "instance_type_id": instance_type_id,
                "pricing_id": pricing_id,
                "always_on": always_on,
                "dr": dr,
                "username": username,
                "password": password,
                "on_init_script": on_init_script,
                "tags": tags or {},
            },
        )

    def update_vm(self, vm_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/compute/virtual_machine/{vm_id}", fields)

    def delete_vm(self, vm_id: str) -> dict | None:
        return self.delete(f"/user/resource/compute/virtual_machine/{vm_id}")

    def list_allocations(self, **filters) -> list[dict]:

        if "vm_id" in filters and "machine_id" not in filters:
            filters["machine_id"] = filters.pop("vm_id")
        return self._paginate(
            "/user/resource/compute/virtual_machine_allocation",
            self._filters(**filters),
        )

    def get_allocation(self, alloc_id: str) -> dict:
        return self.get(f"/user/resource/compute/virtual_machine_allocation/{alloc_id}")

    def create_allocation(self, vm_id: str, tags: dict | None = None) -> dict:
        return self.post(
            "/user/resource/compute/virtual_machine_allocation",
            {**self._scope(), "machine_id": vm_id, "tags": tags or {}},
        )

    def delete_allocation(self, alloc_id: str) -> dict | None:
        return self.delete(
            f"/user/resource/compute/virtual_machine_allocation/{alloc_id}"
        )

    def list_clusters(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/compute/virtual_cluster", self._filters(**filters)
        )

    def get_cluster(self, cluster_id: str) -> dict:
        return self.get(f"/user/resource/compute/virtual_cluster/{cluster_id}")

    def create_cluster(
        self,
        *,
        name: str,
        instance_type_id: str,
        fabric_type: str = "infiniband",
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/compute/virtual_cluster",
            {
                **self._scope(),
                "name": name,
                "instance_type_id": instance_type_id,
                "fabric_type": fabric_type,
                "tags": tags or {},
            },
        )

    def update_cluster(self, cluster_id: str, **fields) -> dict:
        return self.patch(
            f"/user/resource/compute/virtual_cluster/{cluster_id}", fields
        )

    def delete_cluster(self, cluster_id: str) -> dict | None:
        return self.delete(f"/user/resource/compute/virtual_cluster/{cluster_id}")

    def list_cluster_allocations(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/compute/virtual_cluster_allocation",
            self._filters(**filters),
        )

    def get_cluster_allocation(self, alloc_id: str) -> dict:
        return self.get(f"/user/resource/compute/virtual_cluster_allocation/{alloc_id}")

    def create_cluster_allocation(
        self, cluster_id: str, tags: dict | None = None
    ) -> dict:
        return self.post(
            "/user/resource/compute/virtual_cluster_allocation",
            {**self._scope(), "cluster_id": cluster_id, "tags": tags or {}},
        )

    def delete_cluster_allocation(self, alloc_id: str) -> dict | None:
        return self.delete(
            f"/user/resource/compute/virtual_cluster_allocation/{alloc_id}"
        )

    def list_vnets(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/network/virtual_network", self._filters(**filters)
        )

    def get_vnet(self, vnet_id: str) -> dict:
        return self.get(f"/user/resource/network/virtual_network/{vnet_id}")

    def create_vnet(
        self, *, name: str, network_cidr: str, tags: dict | None = None
    ) -> dict:
        return self.post(
            "/user/resource/network/virtual_network",
            {
                **self._scope(),
                "name": name,
                "network_cidr": network_cidr,
                "tags": tags or {},
            },
        )

    def update_vnet(self, vnet_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/network/virtual_network/{vnet_id}", fields)

    def delete_vnet(self, vnet_id: str) -> dict | None:
        return self.delete(f"/user/resource/network/virtual_network/{vnet_id}")

    def list_subnets(self, **filters) -> list[dict]:
        return self._paginate("/user/resource/network/subnet", self._filters(**filters))

    def get_subnet(self, subnet_id: str) -> dict:
        return self.get(f"/user/resource/network/subnet/{subnet_id}")

    def create_subnet(
        self,
        *,
        name: str,
        attached_network_id: str,
        network_gw: str,
        purpose: str = "virtual_machine",
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/network/subnet",
            {
                **self._scope(),
                "name": name,
                "attached_network_id": attached_network_id,
                "purpose": purpose,
                "network_gw": network_gw,
                "tags": tags or {},
            },
        )

    def update_subnet(self, subnet_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/network/subnet/{subnet_id}", fields)

    def delete_subnet(self, subnet_id: str) -> dict | None:
        return self.delete(f"/user/resource/network/subnet/{subnet_id}")

    def list_nics(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/network/network_interface", self._filters(**filters)
        )

    def get_nic(self, nic_id: str) -> dict:
        return self.get(f"/user/resource/network/network_interface/{nic_id}")

    def create_nic(
        self,
        *,
        name: str,
        attached_subnet_id: str,
        ip: str | None = None,
        mac: str | None = None,
        dr: bool = False,
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/network/network_interface",
            {
                **self._scope(),
                "name": name,
                "attached_subnet_id": attached_subnet_id,
                "ip": ip,
                "mac": mac,
                "dr": dr,
                "tags": tags or {},
            },
        )

    def update_nic(self, nic_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/network/network_interface/{nic_id}", fields)

    def attach_nic(self, nic_id: str, machine_id: str | None) -> dict:
        return self.update_nic(nic_id, attached_machine_id=machine_id)

    def delete_nic(self, nic_id: str) -> dict | None:
        return self.delete(f"/user/resource/network/network_interface/{nic_id}")

    def list_public_ips(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/network/public_ip", self._filters(**filters)
        )

    def get_public_ip(self, ip_id: str) -> dict:
        return self.get(f"/user/resource/network/public_ip/{ip_id}")

    def create_public_ip(
        self,
        *,
        pricing_id: str,
        dr: bool = False,
        ddos: bool = True,
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/network/public_ip",
            {
                **self._scope(),
                "pricing_id": pricing_id,
                "dr": dr,
                "ddos": ddos,
                "tags": tags or {},
            },
        )

    def update_public_ip(self, ip_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/network/public_ip/{ip_id}", fields)

    def attach_public_ip(self, ip_id: str, nic_id: str | None) -> dict:
        return self.update_public_ip(ip_id, attached_network_interface_id=nic_id)

    def delete_public_ip(self, ip_id: str) -> dict | None:
        return self.delete(f"/user/resource/network/public_ip/{ip_id}")

    def list_vpns(self, **filters) -> list[dict]:
        return self._paginate("/user/resource/network/vpn", self._filters(**filters))

    def get_vpn(self, vpn_id: str) -> dict:
        return self.get(f"/user/resource/network/vpn/{vpn_id}")

    def create_vpn(self, *, attached_subnet_id: str, tags: dict | None = None) -> dict:
        return self.post(
            "/user/resource/network/vpn",
            {
                **self._scope(),
                "attached_subnet_id": attached_subnet_id,
                "tags": tags or {},
            },
        )

    def delete_vpn(self, vpn_id: str) -> dict | None:
        return self.delete(f"/user/resource/network/vpn/{vpn_id}")

    def list_block_storages(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/block_storage", self._filters(**filters)
        )

    def get_block_storage(self, bs_id: str) -> dict:
        return self.get(f"/user/resource/storage/block_storage/{bs_id}")

    def create_block_storage(
        self,
        *,
        name: str,
        size_gib: int,
        pricing_id: str,
        image_id: str | None = None,
        snapshot_id: str | None = None,
        dr: bool = False,
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/storage/block_storage",
            {
                **self._scope(),
                "name": name,
                "size_gib": size_gib,
                "pricing_id": pricing_id,
                "dr": dr,
                "image_id": image_id,
                "snapshot_id": snapshot_id,
                "tags": tags or {},
            },
        )

    def update_block_storage(self, bs_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/storage/block_storage/{bs_id}", fields)

    def attach_block_storage(self, bs_id: str, machine_id: str | None) -> dict:
        return self.update_block_storage(bs_id, attached_machine_id=machine_id)

    def delete_block_storage(self, bs_id: str) -> dict | None:
        return self.delete(f"/user/resource/storage/block_storage/{bs_id}")

    def list_block_snapshots(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/block_storage/snapshot", self._filters(**filters)
        )

    def get_block_snapshot(self, snapshot_id: str) -> dict:
        return self.get(f"/user/resource/storage/block_storage/snapshot/{snapshot_id}")

    def create_block_snapshot(
        self, *, name: str, block_storage_id: str, tags: dict | None = None
    ) -> dict:
        return self.post(
            "/user/resource/storage/block_storage/snapshot",
            {
                **self._scope(),
                "name": name,
                "block_storage_id": block_storage_id,
                "tags": tags or {},
            },
        )

    def update_block_snapshot(self, snapshot_id: str, **fields) -> dict:
        return self.patch(
            f"/user/resource/storage/block_storage/snapshot/{snapshot_id}", fields
        )

    def delete_block_snapshot(self, snapshot_id: str) -> dict | None:
        return self.delete(
            f"/user/resource/storage/block_storage/snapshot/{snapshot_id}"
        )

    def list_snapshot_schedulers(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/block_storage/snapshot_scheduler",
            self._filters(**filters),
        )

    def get_snapshot_scheduler(self, sched_id: str) -> dict:
        return self.get(
            f"/user/resource/storage/block_storage/snapshot_scheduler/{sched_id}"
        )

    def create_snapshot_scheduler(
        self,
        *,
        name: str,
        block_storage_id: str,
        cron_expression: str,
        max_snapshots: int,
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/storage/block_storage/snapshot_scheduler",
            {
                **self._scope(),
                "name": name,
                "block_storage_id": block_storage_id,
                "cron_expression": cron_expression,
                "max_snapshots": max_snapshots,
                "tags": tags or {},
            },
        )

    def update_snapshot_scheduler(self, sched_id: str, **fields) -> dict:
        return self.patch(
            f"/user/resource/storage/block_storage/snapshot_scheduler/{sched_id}",
            fields,
        )

    def delete_snapshot_scheduler(self, sched_id: str) -> dict | None:
        return self.delete(
            f"/user/resource/storage/block_storage/snapshot_scheduler/{sched_id}"
        )

    def list_object_storages(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/object_storage", self._filters(**filters)
        )

    def get_object_storage(self, os_id: str) -> dict:
        return self.get(f"/user/resource/storage/object_storage/{os_id}")

    def create_object_storage(
        self, *, name: str, size_gib: int, tags: dict | None = None
    ) -> dict:
        return self.post(
            "/user/resource/storage/object_storage",
            {**self._scope(), "name": name, "size_gib": size_gib, "tags": tags or {}},
        )

    def update_object_storage(self, os_id: str, **fields) -> dict:
        return self.patch(f"/user/resource/storage/object_storage/{os_id}", fields)

    def delete_object_storage(self, os_id: str) -> dict | None:
        return self.delete(f"/user/resource/storage/object_storage/{os_id}")

    def list_object_users(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/object_storage/user", self._filters(**filters)
        )

    def get_object_user(self, user_id: str) -> dict:
        return self.get(f"/user/resource/storage/object_storage/user/{user_id}")

    def create_object_user(self, *, name: str, tags: dict | None = None) -> dict:
        return self.post(
            "/user/resource/storage/object_storage/user",
            {**self._scope(), "name": name, "tags": tags or {}},
        )

    def update_object_user(self, user_id: str, **fields) -> dict:
        return self.patch(
            f"/user/resource/storage/object_storage/user/{user_id}", fields
        )

    def delete_object_user(self, user_id: str) -> dict | None:
        return self.delete(f"/user/resource/storage/object_storage/user/{user_id}")

    def list_object_grants(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/object_storage/user_grant", self._filters(**filters)
        )

    def get_object_grant(self, grant_id: str) -> dict:
        return self.get(f"/user/resource/storage/object_storage/user_grant/{grant_id}")

    def create_object_grant(
        self,
        *,
        object_storage_id: str,
        object_storage_user_id: str,
        permission: str,
        tags: dict | None = None,
    ) -> dict:
        return self.post(
            "/user/resource/storage/object_storage/user_grant",
            {
                **self._scope(),
                "object_storage_id": object_storage_id,
                "object_storage_user_id": object_storage_user_id,
                "permission": permission,
                "tags": tags or {},
            },
        )

    def update_object_grant(self, grant_id: str, **fields) -> dict:
        return self.patch(
            f"/user/resource/storage/object_storage/user_grant/{grant_id}", fields
        )

    def delete_object_grant(self, grant_id: str) -> dict | None:
        return self.delete(
            f"/user/resource/storage/object_storage/user_grant/{grant_id}"
        )

    def list_pfs(self, **filters) -> list[dict]:
        return self._paginate(
            "/user/resource/storage/parallel_file_system", self._filters(**filters)
        )

    def get_pfs(self, pfs_id: str) -> dict:
        return self.get(f"/user/resource/storage/parallel_file_system/{pfs_id}")

    def create_pfs(self, *, name: str, size_gib: int, tags: dict | None = None) -> dict:
        return self.post(
            "/user/resource/storage/parallel_file_system",
            {**self._scope(), "name": name, "size_gib": size_gib, "tags": tags or {}},
        )

    def update_pfs(self, pfs_id: str, **fields) -> dict:
        return self.patch(
            f"/user/resource/storage/parallel_file_system/{pfs_id}", fields
        )

    def delete_pfs(self, pfs_id: str) -> dict | None:
        return self.delete(f"/user/resource/storage/parallel_file_system/{pfs_id}")

    def list_pfs_members(self, **filters) -> list[dict]:
        if "pfs_id" in filters and "parallel_file_system_id" not in filters:
            filters["parallel_file_system_id"] = filters.pop("pfs_id")
        return self._paginate(
            "/user/resource/storage/parallel_file_system/member",
            self._filters(**filters),
        )

    def get_pfs_member(self, member_id: str) -> dict:
        return self.get(
            f"/user/resource/storage/parallel_file_system/member/{member_id}"
        )

    def create_pfs_member(
        self, *, pfs_id: str, machine_id: str, tags: dict | None = None
    ) -> dict:
        return self.post(
            "/user/resource/storage/parallel_file_system/member",
            {
                **self._scope(),
                "parallel_file_system_id": pfs_id,
                "machine_id": machine_id,
                "tags": tags or {},
            },
        )

    def delete_pfs_member(self, member_id: str) -> dict | None:
        return self.delete(
            f"/user/resource/storage/parallel_file_system/member/{member_id}"
        )

    def wait_for_status(
        self,
        fetch: Callable[[], dict],
        target_statuses: set[str],
        *,
        timeout: float = 300.0,
        interval: float = 3.0,
    ) -> dict:
        deadline = time.monotonic() + timeout
        last: dict = {}

        while time.monotonic() < deadline:
            last = fetch()
            if last.get("status") in target_statuses:
                return last
            time.sleep(interval)

        raise TimeoutError(
            f"status {last.get('status')!r} did not reach {target_statuses} in {timeout}s"
        )
