"""Session routes V2 — aligned with openapi.yaml (/v1/session/...)."""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.schemas import (
    SessionStartRequest,
    Envelope,
    Meta,
    QuestionPayload,
    ResultPayload,
    EmergencyPayload,
    ErrorPayload,
    UiHints,
    ChatMessage,
    SummaryResponse,
)
from app.models.database import get_db, SessionModel, MessageModel, ResultModel
from app.agents.orchestrator import orchestrator
from app.services.facility_discovery import discover_facilities, DEFAULT_CITY
from app.api.routes.legacy_deprecation import (
    apply_legacy_deprecation_headers,
    log_legacy_route_hit,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DISCLAIMER = "Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır."


def _make_meta(debug: dict = None, facility_discovery: Optional[dict] = None) -> Meta:
    return Meta(
        disclaimer_tr=DISCLAIMER,
        timestamp=datetime.now(timezone.utc),
        debug=debug,
        facility_discovery=facility_discovery,
    )


@router.post("/session/start", response_model=Envelope)
async def start_session(
    request: SessionStartRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Start a new triage session with initial symptoms."""
    apply_legacy_deprecation_headers(response)
    log_legacy_route_hit(logger, "/v1/session/start")
    session_id = str(uuid.uuid4())

    db_session = SessionModel(
        id=session_id,
        status="chatting",
        profile_json=request.profile.model_dump() if request.profile else None,
    )
    db.add(db_session)

    user_msg = MessageModel(
        session_id=session_id,
        role="user",
        content=request.user_input_tr,
    )
    db.add(user_msg)

    try:
        # Map new Profile to UserProfile for orchestrator
        profile = request.profile
        result = await orchestrator.handle_initial_symptoms(
            session_id=session_id,
            symptoms_text=request.user_input_tr,
            profile=profile,
        )

        if result.action == "emergency":
            db_session.status = "emergency"
            ai_msg = MessageModel(
                session_id=session_id, role="ai", content=result.message,
                metadata_json={"type": "emergency"},
            )
            db.add(ai_msg)
            await db.commit()

            return Envelope(
                type="EMERGENCY",
                session_id=session_id,
                payload=EmergencyPayload(
                    reason_tr=result.emergency.reason if result.emergency else "",
                    instructions_tr=result.emergency.emergency_instructions if result.emergency else [],
                    missing_info_to_confirm_tr=result.emergency.missing_info_to_confirm if result.emergency else [],
                ).model_dump(),
                meta=_make_meta(),
            )

        if result.action == "result":
            db_session.status = "done"
            ai_msg = MessageModel(
                session_id=session_id, role="ai", content=result.message,
                metadata_json={"type": "result"},
            )
            db.add(ai_msg)
            state = orchestrator.get_session(session_id)
            if state and state.reasoning_output and state.routing_output:
                db_result = ResultModel(
                    session_id=session_id,
                    candidates_json=[c.model_dump() for c in state.reasoning_output.candidates],
                    routing_json=state.routing_output.model_dump(),
                    risk_level=state.reasoning_output.risk_level,
                )
                db.add(db_result)
            await db.commit()
            return _build_result_envelope(session_id, state)

        # Question
        ai_msg = MessageModel(
            session_id=session_id, role="ai", content=result.message,
            metadata_json={"type": "question"},
        )
        db.add(ai_msg)

        state = orchestrator.get_session(session_id)
        if state and state.structured_symptoms:
            db_session.symptoms_json = state.structured_symptoms.model_dump()

        await db.commit()

        # Build ui_hints
        answer_type = result.question.answer_type if result.question else "free_text"
        ui_hints = None
        if answer_type == "yes_no":
            ui_hints = UiHints(quick_replies=True)

        return Envelope(
            type="QUESTION",
            session_id=session_id,
            payload=QuestionPayload(
                question_tr=result.question.question_tr if result.question else result.message,
                answer_type=answer_type,
                choices_tr=result.question.choices_tr if result.question else [],
                ui_hints=ui_hints,
            ).model_dump(),
            meta=_make_meta(),
        )

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        await db.rollback()
        return Envelope(
            type="ERROR",
            session_id=session_id,
            payload=ErrorPayload(code="START_FAILED", message_tr=str(e)).model_dump(),
            meta=_make_meta(),
        )


@router.get("/session/{session_id}/result", response_model=Envelope)
async def get_result(
    session_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Get the analysis result for a completed session."""
    apply_legacy_deprecation_headers(response)
    log_legacy_route_hit(logger, "/v1/session/{session_id}/result", session_id)
    state = orchestrator.get_session(session_id)
    if not state or not state.is_complete or not state.reasoning_output:
        raise HTTPException(status_code=400, detail="Analysis not yet complete")

    return _build_result_envelope(session_id, state)


@router.get("/session/{session_id}/summary", response_model=SummaryResponse)
async def get_summary(
    session_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Get the doctor-ready summary for a completed session."""
    apply_legacy_deprecation_headers(response)
    log_legacy_route_hit(logger, "/v1/session/{session_id}/summary", session_id)
    state = orchestrator.get_session(session_id)
    if not state or not state.is_complete or not state.routing_output:
        raise HTTPException(status_code=400, detail="Analysis not yet complete")

    msg_result = await db.execute(
        select(MessageModel)
        .where(MessageModel.session_id == session_id)
        .order_by(MessageModel.created_at)
    )
    messages = [
        ChatMessage(role=m.role, content=m.content, timestamp=m.created_at, metadata=m.metadata_json)
        for m in msg_result.scalars().all()
    ]

    return SummaryResponse(
        session_id=session_id,
        doctor_ready_summary_tr=state.routing_output.doctor_ready_summary_tr,
        candidates=state.reasoning_output.candidates,
        routing=state.routing_output,
        messages=messages,
    )


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str, response: Response):
    """Debug endpoint: get full session state snapshot."""
    apply_legacy_deprecation_headers(response)
    log_legacy_route_hit(logger, "/v1/session/{session_id}/state", session_id)
    state = orchestrator.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state.to_state_dict()


def _resolve_specialty_key_from_state(state) -> Optional[str]:
    if not state:
        return None

    top_specialty = getattr(state, "top_specialty", None)
    if isinstance(top_specialty, dict) and top_specialty.get("id"):
        return str(top_specialty["id"])

    final_scores = getattr(state, "final_specialty_scores", None)
    if isinstance(final_scores, dict) and final_scores:
        ranked = sorted(
            final_scores.items(),
            key=lambda kv: float((kv[1] or {}).get("final_score", 0.0)),
            reverse=True,
        )
        if ranked:
            return str(ranked[0][0])

    return None


def _build_facility_discovery(state) -> Optional[dict]:
    specialty_key = _resolve_specialty_key_from_state(state)
    if not specialty_key:
        return None

    try:
        return discover_facilities(city=DEFAULT_CITY, specialty_key=specialty_key, limit=5)
    except Exception as e:
        logger.warning("Facility discovery failed for session %s: %s", state.session_id, e)
        return None


def _build_result_envelope(session_id: str, state) -> Envelope:
    """Build a RESULT Envelope from session state."""
    facility_discovery = _build_facility_discovery(state)
    return Envelope(
        type="RESULT",
        session_id=session_id,
        payload=ResultPayload(
            recommended_specialty_tr=state.routing_output.recommended_specialty_tr,
            urgency=state.routing_output.urgency,
            candidates_tr=state.reasoning_output.candidates,
            rationale_tr=state.routing_output.rationale_tr,
            emergency_watchouts_tr=state.routing_output.emergency_watchouts_tr,
            doctor_ready_summary_tr=state.routing_output.doctor_ready_summary_tr,
            specialty_scores=state.specialty_scores,
        ).model_dump(),
        meta=_make_meta(facility_discovery=facility_discovery),
    )
