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
    since_days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    tool = StatsTool(db)
    return await tool.get_summary(since_days=since_days)
