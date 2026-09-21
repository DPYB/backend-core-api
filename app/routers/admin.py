import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.demo_reset_service import DemoResetService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def verify_admin_key(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> str:
    """X-Admin-Key 헤더 검증 (비교 타이밍 공격 방지를 위한 secrets.compare_digest 사용)"""
    if not x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="관리자 API 인증 헤더(X-Admin-Key)가 필요합니다.",
        )
    expected_key = settings.ADMIN_API_KEY
    if not expected_key or not secrets.compare_digest(x_admin_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 API 키가 유효하지 않습니다.",
        )
    return x_admin_key


@router.post(
    "/demo/reset",
    status_code=status.HTTP_200_OK,
    summary="데모 계정 서재 및 시연 데이터 멱등 리셋",
    description="시드 도서 16종 외 잉여 데이터 정리 및 진도율/완독상태를 시드 기준값으로 원복합니다.",
)
async def reset_demo_account(
    _: str = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await DemoResetService.reset_demo_account(db)
