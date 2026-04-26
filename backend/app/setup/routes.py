"""Route registration — every router included with /v1 prefix.

Adding a new router is one import + one `app.include_router()` call.
Tags map to OpenAPI groupings; the `/v1` prefix is uniform so
clients always see `/v1/<resource>`.

Note on admin_v5_router: it carries its own internal `prefix="/admin"`,
so we mount it under `/v1` to land its endpoints at `/v1/admin/*`. This
matters because `admin_rate_limit_middleware` gates `/v1/admin/*`; if
admin_v5 were registered without the `/v1` prefix it would slip past
the admin rate limit.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.admin_api import router as admin_router
from app.admin_feedback_api import router as admin_feedback_router
from app.admin_tenants_api import router as admin_tenants_router
from app.admin_v5 import router as admin_v5_router
from app.api.routes.data_rights import router as data_rights_router
from app.api.routes.facilities import router as facilities_router
from app.api.routes.features import router as features_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.health_tourism import router as health_tourism_router
from app.api.routes.message import router as message_router
from app.api.routes.push_token import router as push_token_router
from app.api.routes.session import router as session_router
from app.api.routes.summary_email import router as summary_email_router
from app.api.routes.triage import router as triage_router


def register_routes(app: FastAPI) -> None:
    app.include_router(triage_router, prefix="/v1", tags=["Triage"])
    app.include_router(feedback_router, prefix="/v1", tags=["Feedback"])
    app.include_router(facilities_router, prefix="/v1", tags=["Facilities"])
    app.include_router(summary_email_router, prefix="/v1", tags=["Summary Email"])
    app.include_router(push_token_router, prefix="/v1", tags=["Push Token"])
    app.include_router(features_router, prefix="/v1", tags=["Config"])
    app.include_router(health_tourism_router, prefix="/v1", tags=["Health Tourism"])
    app.include_router(session_router, prefix="/v1", tags=["Session (legacy)"])
    app.include_router(message_router, prefix="/v1", tags=["Message (legacy)"])
    app.include_router(admin_router, prefix="/v1", tags=["Admin"])
    app.include_router(admin_tenants_router, prefix="/v1", tags=["Admin Tenants"])
    app.include_router(admin_feedback_router, prefix="/v1", tags=["Admin Feedback"])
    app.include_router(data_rights_router, prefix="/v1", tags=["Data Rights"])
    app.include_router(admin_v5_router, prefix="/v1", tags=["Admin V5"])
