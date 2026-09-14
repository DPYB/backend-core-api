from pydantic import Field

from app.schemas.common import CamelModel


class SocialLoginRequest(CamelModel):
    """소셜 로그인 요청 (Google id_token 또는 Kakao access_token)"""

    token: str = Field(
        ..., min_length=1, description="Google id_token 또는 Kakao access_token"
    )
    agreed_terms_ids: list[int] = Field(
        default_factory=list, description="가입 시 동의한 약관 ID 목록 (선택)"
    )


class TokenResponse(CamelModel):
    """자체 발급 JWT 토큰 응답"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    member_id: str
    is_new_member: bool


class RefreshTokenRequest(CamelModel):
    """토큰 갱신 요청"""

    refresh_token: str = Field(
        ..., min_length=1, description="기존 발급받은 Refresh Token"
    )


class AvailabilityRequest(CamelModel):
    """이메일 또는 닉네임 중복 확인 요청"""

    field: str = Field(..., description="'email' 또는 'nickname'")
    value: str = Field(..., min_length=1, max_length=255, description="중복 확인할 값")


class AvailabilityResponse(CamelModel):
    """중복 확인 응답"""

    field: str
    value: str
    is_available: bool
    message: str
