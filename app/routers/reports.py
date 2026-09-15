import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_authenticated_member_id
from app.db.session import get_db
from app.schemas.report import MonthlyReportStatsResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get(
    "/monthly-stats",
    response_model=MonthlyReportStatsResponse,
    summary="사서 월간 독서 리포트 원천 통계 집계 조회",
)
async def get_monthly_report_stats(
    year: int = Query(..., ge=2020, le=2100, description="조회 연도 (예: 2026)"),
    month: int = Query(..., ge=1, le=12, description="조회 월 (1~12)"),
    member_id: uuid.UUID = Depends(get_authenticated_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_monthly_stats(db, member_id, year, month)
