from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class TermsResponse(CamelModel):
    """약관 목록 응답 항목"""

    terms_id: int
    code: str
    name: str
    content: str
    is_required: bool
    effective_at: datetime


class TermsAgreementRequest(CamelModel):
    """약관 동의 또는 철회 요청"""

    terms_id: int = Field(..., description="약관 ID")
    action: str = Field("AGREE", description="AGREE 또는 WITHDRAW")


class TermsAgreementResponse(CamelModel):
    """약관 동의 결과 응답"""

    success: bool
    terms_id: int
    action: str
    occurred_at: datetime
