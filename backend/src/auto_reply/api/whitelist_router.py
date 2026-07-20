"""
whitelist_router.py — REST API for Whitelist Management.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.tools.bulk_import_tool import BulkImportReport, BulkImportTool
from src.auto_reply.tools.matcher_tool import invalidate_whitelist_cache
from src.auto_reply.tools.whitelist_tool import (
    WhitelistDuplicateError,
    WhitelistEntryNotFound,
    WhitelistTool,
    WhitelistValidationError,
)
from src.auto_reply.workflow.rescan import request_rescan
from src.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whitelist", tags=["whitelist"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WhitelistEntryCreate(BaseModel):
    value: str = Field(..., description="Email address or @domain.com")


class WhitelistEntryUpdate(BaseModel):
    value: str | None = None


class WhitelistEntryResponse(BaseModel):
    id: int
    entry_type: str
    value: str
    created_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> WhitelistEntryResponse:
        return cls(
            id=obj.id,
            entry_type=obj.entry_type.value,
            value=obj.value,
            created_at=obj.created_at.isoformat(),
        )


class PaginatedWhitelistResponse(BaseModel):
    items: list[WhitelistEntryResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedWhitelistResponse)
async def list_whitelist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entry_type: str | None = Query(None, description="'email' or 'domain'"),
    db: AsyncSession = Depends(get_db),
):
    tool = WhitelistTool(db)
    items, total = await tool.list_entries(entry_type=entry_type, page=page, page_size=page_size)
    return PaginatedWhitelistResponse(
        items=[WhitelistEntryResponse.from_orm(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{entry_id}", response_model=WhitelistEntryResponse)
async def get_whitelist_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    tool = WhitelistTool(db)
    try:
        entry = await tool.get_entry(entry_id)
        return WhitelistEntryResponse.from_orm(entry)
    except WhitelistEntryNotFound:
        raise HTTPException(status_code=404, detail="Entry not found")


@router.post("", response_model=WhitelistEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_whitelist_entry(
    payload: WhitelistEntryCreate, db: AsyncSession = Depends(get_db)
):
    tool = WhitelistTool(db)
    try:
        entry = await tool.create_entry(value=payload.value)
        invalidate_whitelist_cache()
        # Note: adding a rule does *not* re-examine mail already filed as
        # skipped. That sweep drafts real replies, so it stays an explicit
        # action — POST /rescan.
        return WhitelistEntryResponse.from_orm(entry)
    except WhitelistValidationError as e:
        raise HTTPException(status_code=422, detail=e.args[0])
    except WhitelistDuplicateError as e:
        raise HTTPException(status_code=409, detail=e.args[0])


@router.put("/{entry_id}", response_model=WhitelistEntryResponse)
async def update_whitelist_entry(
    entry_id: int, payload: WhitelistEntryUpdate, db: AsyncSession = Depends(get_db)
):
    tool = WhitelistTool(db)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    try:
        entry = await tool.update_entry(entry_id, **fields)
        invalidate_whitelist_cache()
        return WhitelistEntryResponse.from_orm(entry)
    except WhitelistEntryNotFound:
        raise HTTPException(status_code=404, detail="Entry not found")
    except WhitelistValidationError as e:
        raise HTTPException(status_code=422, detail=e.args[0])
    except WhitelistDuplicateError as e:
        raise HTTPException(status_code=409, detail=e.args[0])


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_whitelist_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    tool = WhitelistTool(db)
    try:
        await tool.delete_entry(entry_id)
        invalidate_whitelist_cache()
    except WhitelistEntryNotFound:
        raise HTTPException(status_code=404, detail="Entry not found")


@router.post("/rescan", status_code=status.HTTP_202_ACCEPTED)
async def rescan_skipped_mail():
    """Re-examine recently skipped mail against the current whitelist.

    Deliberately the only way a rescan starts. Whitelist writes do not trigger
    one: the sweep re-fetches messages from Gmail, calls the LLM and files real
    drafts in the mailbox, and adding a rule should not do all that as a side
    effect. Bounded by `whitelist_rescan_lookback_hours`.

    202, not 200: the sweep runs on the background worker and its result is not
    known when this returns. Watch the Logs panel for the outcome.
    """
    request_rescan()
    return {"status": "accepted"}


@router.post("/import")
async def bulk_import_whitelist(
    file: Annotated[UploadFile, File(...)],
    db: AsyncSession = Depends(get_db),
):
    """Import whitelist entries from a CSV or Excel file."""
    tool = BulkImportTool(db)
    file_bytes = await file.read()
    
    # Simple content-type / extension check
    filename = file.filename or ""
    if filename.endswith(".csv") or file.content_type == "text/csv":
        report = await tool.import_csv(file_bytes)
    elif filename.endswith((".xlsx", ".xls")) or "spreadsheet" in (file.content_type or ""):
        report = await tool.import_excel(file_bytes)
    else:
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Must be CSV or Excel."
        )

    if report.inserted > 0:
        invalidate_whitelist_cache()

    # We can return the dataclass directly; FastAPI will convert it to JSON
    return report
