from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.record import RecordCreateRequest, RecordResponse
from app.services.record_service import record_service

router = APIRouter(prefix="/api/v1/records", tags=["records"])


@router.post("", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    request: RecordCreateRequest,
    x_member_id: UUID = Header(
        ..., alias="X-Member-Id", description="회원 식별자 UUID"
    ),
    db: AsyncSession = Depends(get_db),
):
    """독서 기록 및 스크랩 최종 저장."""
    return await record_service.create_record(db, x_member_id, request)


@router.get("", response_model=list[RecordResponse])
async def list_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    x_member_id: UUID = Header(
        ..., alias="X-Member-Id", description="회원 식별자 UUID"
    ),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 독서 기록 목록 조회 (페이징)."""
    return await record_service.get_records(db, x_member_id, skip=skip, limit=limit)


@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: int,
    x_member_id: UUID = Header(
        ..., alias="X-Member-Id", description="회원 식별자 UUID"
    ),
    db: AsyncSession = Depends(get_db),
):
    """독서 기록 단건 상세 조회."""
    record = await record_service.get_record_by_id(db, x_member_id, record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="독서 기록을 찾을 수 없습니다.",
        )
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(
    record_id: int,
    x_member_id: UUID = Header(
        ..., alias="X-Member-Id", description="회원 식별자 UUID"
    ),
    db: AsyncSession = Depends(get_db),
):
    """독서 기록 소프트 삭제 (연결된 스크랩도 함께 소프트 삭제 처리)."""
    success = await record_service.delete_record(db, x_member_id, record_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="독서 기록을 찾을 수 없습니다.",
        )
    return None
