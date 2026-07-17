"""
gmail_router.py — Push-mode endpoint for receiving inbound emails.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent, get_gmail_adapter

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class InboundEmailPayload(BaseModel):
    gmail_message_id: str = Field(..., max_length=256)
    gmail_thread_id: str | None = Field(None, max_length=256)
    sender_email: str = Field(..., max_length=320)
    sender_name: str | None = Field(None, max_length=200)
    subject: str | None = Field(None, max_length=998)
    body_text: str | None = None
    body_html: str | None = None
    received_at: datetime
    to_recipients: list[str] = Field(default_factory=list)
    cc_recipients: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/incoming", status_code=202)
async def push_incoming_email(payload: InboundEmailPayload) -> dict[str, Any]:
    """Push an inbound email payload into the AutoReply workflow."""
    event = InboundEmailEvent(
        gmail_message_id=payload.gmail_message_id,
        gmail_thread_id=payload.gmail_thread_id,
        sender_email=payload.sender_email,
        sender_name=payload.sender_name,
        subject=payload.subject,
        body_text=payload.body_text,
        body_html=payload.body_html,
        received_at=payload.received_at,
        to_recipients=payload.to_recipients,
        cc_recipients=payload.cc_recipients,
    )
    
    adapter = get_gmail_adapter()
    enqueued = await adapter.enqueue(event)
    
    if not enqueued:
        raise HTTPException(
            status_code=429,
            detail="Queue is full or message was already processed.",
        )
        
    return {"status": "enqueued"}
