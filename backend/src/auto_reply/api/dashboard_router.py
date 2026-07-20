"""
dashboard_router.py — REST API for AutoReply statistics.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.tools.stats_tool import DashboardSummary, StatsTool
from src.database import get_db

router = APIRouter(prefix="/api/v1/auto-reply/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    # Hours, not days: the panel's shortest window is 1h, which `since_days`
    # could not express at all — its floor was a whole day. 8760 is a year.
    since_hours: int = Query(24, ge=1, le=8760),
    db: AsyncSession = Depends(get_db),
):
    tool = StatsTool(db)
    return await tool.get_summary(since_hours=since_hours)
