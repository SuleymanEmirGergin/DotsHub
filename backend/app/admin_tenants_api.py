"""C2 multi-tenant catalog admin API.

Endpoints:
    GET  /v1/admin/tenants                       — list tenants
    GET  /v1/admin/tenants/{tenant_id}/curated   — read catalog
    PUT  /v1/admin/tenants/{tenant_id}/curated   — replace catalog
    POST /v1/admin/tenants                       — create new tenant
                                                   (writes an empty-
                                                   conditions catalog)

Auth: x-admin-key header, same pattern as admin_api.py.

Catalog files live at:
    backend/app/data/curated_conditions.<tenant_id>.json

The "default" tenant is stored as curated_conditions.json (no suffix)
to stay backward-compatible with C2-era loads that predate C1. Both
paths are accepted on read; writes to "default" go to the canonical
unsuffixed path.

Tenant id validation: [a-z0-9_-]{1,32}. Rejects filesystem-unsafe
characters explicitly — this endpoint writes a file whose name
contains the tenant id.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.admin_auth import require_admin_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/tenants", tags=["Admin Tenants"])

# Anchor the data dir to this file, mirroring runtime.py's _REPO_ROOT
# approach — this endpoint must not depend on process cwd.
_DATA_DIR = Path(__file__).resolve().parent / "data"

_TENANT_ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


# ── Auth ───────────────────────────────────────────────────────────────

def require_admin(x_admin_key: str | None = Header(default=None)):
    return require_admin_key(x_admin_key)


# ── Validation ─────────────────────────────────────────────────────────

def _validate_tenant_id(tenant_id: str) -> None:
    if not _TENANT_ID_RE.match(tenant_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid tenant_id {tenant_id!r}: must match [a-z0-9_-]{{1,32}}"
            ),
        )


def _catalog_path_for(tenant_id: str) -> Path:
    if tenant_id == "default":
        return _DATA_DIR / "curated_conditions.json"
    return _DATA_DIR / f"curated_conditions.{tenant_id}.json"


# ── Schemas ────────────────────────────────────────────────────────────

class TenantEntry(BaseModel):
    tenant_id: str
    path: str
    condition_count: int
    tenant_scope: Optional[str] = None
    disclaimer_tr: Optional[str] = None


class TenantsListResponse(BaseModel):
    tenants: List[TenantEntry]


class ConditionPayload(BaseModel):
    icd10: Optional[str] = None
    disease_description_tr: Optional[str] = None
    doktora_sorulacak_sorular_tr: List[str] = Field(default_factory=list)
    izlenecek_belirtiler_tr: List[str] = Field(default_factory=list)
    ne_zaman_tekrar_basvur_tr: List[str] = Field(default_factory=list)
    self_care_tr: List[str] = Field(default_factory=list)
    aciliyet_notu_tr: Optional[str] = None


class CatalogPayload(BaseModel):
    version: str = "1.0"
    language: str = "tr-TR"
    description: Optional[str] = None
    tenant_scope: Optional[str] = None
    disclaimer_tr: str = (
        "Bu liste tanı değildir, yalnızca hazırlık amaçlıdır. Kesin "
        "değerlendirme için lütfen hekiminize başvurun."
    )
    conditions: Dict[str, ConditionPayload] = Field(default_factory=dict)


class CreateTenantRequest(BaseModel):
    tenant_id: str
    disclaimer_tr: Optional[str] = None
    seed_from_default: bool = False


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=TenantsListResponse)
def list_tenants(admin=Depends(require_admin)):
    """List all tenants with a catalog file."""
    del admin
    tenants: list[TenantEntry] = []

    default_path = _catalog_path_for("default")
    if default_path.exists():
        tenants.append(_tenant_entry_from_file("default", default_path))

    for path in sorted(_DATA_DIR.glob("curated_conditions.*.json")):
        # Example: curated_conditions.demo_hospital.json → demo_hospital
        name = path.stem  # curated_conditions.demo_hospital
        if not name.startswith("curated_conditions."):
            continue
        tenant_id = name[len("curated_conditions."):]
        if not tenant_id or tenant_id == "json":
            # Guard against curated_conditions.json — already handled above
            continue
        if not _TENANT_ID_RE.match(tenant_id):
            logger.warning("Skipping tenant file with invalid id: %s", path.name)
            continue
        tenants.append(_tenant_entry_from_file(tenant_id, path))

    return TenantsListResponse(tenants=tenants)


def _tenant_entry_from_file(tenant_id: str, path: Path) -> TenantEntry:
    condition_count = 0
    tenant_scope: Optional[str] = None
    disclaimer_tr: Optional[str] = None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            conditions = raw.get("conditions") or {}
            condition_count = len(conditions) if isinstance(conditions, dict) else 0
            tenant_scope = raw.get("tenant_scope")
            disclaimer_tr = raw.get("disclaimer_tr")
    except Exception as exc:
        logger.warning("Failed to read tenant file %s: %s", path, exc)
    return TenantEntry(
        tenant_id=tenant_id,
        path=str(path.name),
        condition_count=condition_count,
        tenant_scope=tenant_scope,
        disclaimer_tr=disclaimer_tr,
    )


@router.get("/{tenant_id}/curated")
def get_tenant_catalog(tenant_id: str, admin=Depends(require_admin)) -> Dict[str, Any]:
    """Return the raw catalog JSON for a tenant."""
    del admin
    _validate_tenant_id(tenant_id)
    path = _catalog_path_for(tenant_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No catalog for tenant {tenant_id!r}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read catalog for %s: %s", tenant_id, exc)
        raise HTTPException(status_code=500, detail="catalog read failed") from exc


@router.put("/{tenant_id}/curated")
def put_tenant_catalog(
    tenant_id: str,
    payload: CatalogPayload,
    admin=Depends(require_admin),
) -> Dict[str, Any]:
    """Replace a tenant catalog wholesale. The old file is overwritten."""
    _validate_tenant_id(tenant_id)
    path = _catalog_path_for(tenant_id)
    payload_dict = payload.model_dump(exclude_none=False)
    # Normalize tenant_scope so the file matches the URL tenant id.
    payload_dict["tenant_scope"] = tenant_id
    try:
        path.write_text(
            json.dumps(payload_dict, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "Updated curated catalog for tenant=%r by admin=%r — %d conditions",
            tenant_id,
            admin.get("user_id") if isinstance(admin, dict) else None,
            len(payload_dict.get("conditions", {})),
        )
    except Exception as exc:
        logger.error("Failed to write catalog for %s: %s", tenant_id, exc)
        raise HTTPException(status_code=500, detail="catalog write failed") from exc
    return {"ok": True, "tenant_id": tenant_id, "condition_count": len(payload_dict.get("conditions", {}))}


@router.post("", status_code=201)
def create_tenant(
    req: CreateTenantRequest,
    admin=Depends(require_admin),
) -> Dict[str, Any]:
    """Create a new tenant with an empty or default-seeded catalog."""
    del admin
    _validate_tenant_id(req.tenant_id)
    if req.tenant_id == "default":
        raise HTTPException(status_code=400, detail="tenant_id 'default' is reserved")
    path = _catalog_path_for(req.tenant_id)
    if path.exists():
        raise HTTPException(status_code=409, detail="Tenant already exists")

    base: Dict[str, Any]
    if req.seed_from_default:
        default_path = _catalog_path_for("default")
        try:
            base = json.loads(default_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail="failed to seed from default"
            ) from exc
    else:
        base = {
            "version": "1.0",
            "language": "tr-TR",
            "description": f"{req.tenant_id} tenant curated catalog",
            "conditions": {},
        }
    base["tenant_scope"] = req.tenant_id
    if req.disclaimer_tr:
        base["disclaimer_tr"] = req.disclaimer_tr

    try:
        path.write_text(
            json.dumps(base, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Created tenant %r (seed_from_default=%s)", req.tenant_id, req.seed_from_default)
    except Exception as exc:
        logger.error("Failed to create tenant %s: %s", req.tenant_id, exc)
        raise HTTPException(status_code=500, detail="tenant create failed") from exc
    return {"ok": True, "tenant_id": req.tenant_id, "path": path.name}
