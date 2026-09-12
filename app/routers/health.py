from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(response: Response, db: AsyncSession = Depends(get_db)):
    """
    무과금 배포 정책 준수 헬스체크 엔드포인트:
    - Render 15분 무활동 슬립 방지 (인바운드 HTTP 트래픽)
    - Supabase 7일 비활성화 슬립 방지 (SELECT 1 쿼리 실행)
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "UP", "database": "connected"}
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "DOWN", "database": "disconnected", "detail": str(e)}
