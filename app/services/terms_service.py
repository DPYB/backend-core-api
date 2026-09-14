import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.terms import MemberAgreement, Terms
from app.schemas.terms import TermsAgreementResponse, TermsResponse


class TermsService:
    @staticmethod
    async def get_active_terms(db: AsyncSession) -> list[TermsResponse]:
        """현재 활성 상태인 약관 목록을 반환합니다."""
        now = datetime.now(UTC)
        stmt = (
            select(Terms)
            .where(
                Terms.effective_at <= now,
                Terms.expired_at.is_(None),
                Terms.deleted_at.is_(None),
            )
            .order_by(Terms.id.asc())
        )
        res = await db.execute(stmt)
        terms_list = res.scalars().all()
        return [
            TermsResponse(
                terms_id=t.id,
                code=t.code,
                name=t.name,
                content=t.content,
                is_required=t.is_required,
                effective_at=t.effective_at,
            )
            for t in terms_list
        ]

    @staticmethod
    async def record_agreement(
        db: AsyncSession, member_id: uuid.UUID, terms_id: int, action: str = "AGREE"
    ) -> TermsAgreementResponse:
        """약관 동의 또는 철회 이력을 기록합니다."""
        # 1. 약관 존재 여부 확인
        stmt = select(Terms).where(Terms.id == terms_id, Terms.deleted_at.is_(None))
        res = await db.execute(stmt)
        terms = res.scalars().first()
        if not terms:
            raise AppException(404, "TERMS_NOT_FOUND", "존재하지 않는 약관입니다.")

        if action not in ("AGREE", "WITHDRAW"):
            raise AppException(
                400,
                "INVALID_ACTION",
                "약관 액션은 'AGREE' 또는 'WITHDRAW'만 가능합니다.",
            )

        # 필수 약관 철회 시도시 방어
        if terms.is_required and action == "WITHDRAW":
            raise AppException(
                400, "CANNOT_WITHDRAW_REQUIRED_TERMS", "필수 약관은 철회할 수 없습니다."
            )

        now = datetime.now(UTC)
        agreement = MemberAgreement(
            member_id=member_id,
            terms_id=terms_id,
            action=action,
            occurred_at=now,
        )
        db.add(agreement)
        await db.commit()

        return TermsAgreementResponse(
            success=True,
            terms_id=terms_id,
            action=action,
            occurred_at=now,
        )
