"""Pydantic models for the Supabase-backed triage turn endpoint."""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from uuid import UUID


class AnswerIn(BaseModel):
    canonical: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)


class TriageTurnIn(BaseModel):
    session_id: Optional[UUID] = None
    locale: Literal["tr-TR"] = "tr-TR"
    user_message: str = Field(default="", max_length=4000)
    answer: Optional[AnswerIn] = None


class EnvelopeOut(BaseModel):
    type: Literal["QUESTION", "RESULT", "EMERGENCY", "ERROR"]
    session_id: UUID
    turn_index: int
    payload: Dict[str, Any]
