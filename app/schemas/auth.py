from pydantic import Field, computed_field

from app.schemas.common import CamelModel
from app.schemas.member import MemberProfileResponse


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

    @computed_field(alias="access_token")  # type: ignore[prop-decorator]
    @property
    def access_token_snake(self) -> str:
        return self.access_token

    @computed_field(alias="refresh_token")  # type: ignore[prop-decorator]
    @property
    def refresh_token_snake(self) -> str:
        return self.refresh_token


class LoginRequest(CamelModel):
    """이메일/비밀번호 로그인 요청 (프론트엔드 및 개발/테스트 호환)"""

    email: str = Field(..., min_length=1, description="이메일 주소")
    password: str = Field(default="", description="비밀번호 (개발용 임의값)")


class LoginResponse(TokenResponse):
    """로그인 응답 (토큰 + 회원 프로필 정보)"""

    member: MemberProfileResponse | None = None


class RefreshTokenRequest(CamelModel):
    """토큰 갱신 요청 (바디 또는 쿠키로 전달)"""

    refresh_token: str | None = Field(
        default=None, description="기존 발급받은 Refresh Token"
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


class GuestLoginRequest(CamelModel):
    """게스트 토큰 발급/연장 요청 (세션 유지를 위한 guest_id 옵셔널)"""

    guest_id: str | None = Field(
        default=None,
        description="기존 발급받은 guest_id (UUID 형태). 전달 시 해당 세션의 만료시간을 연장합니다.",
    )


class GuestLoginResponse(CamelModel):
    """게스트 토큰 발급 응답"""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int
    guest_id: str
    sub: str
    role: str = "guest"
    is_guest: bool = True

    @computed_field(alias="access_token")  # type: ignore[prop-decorator]
    @property
    def access_token_snake(self) -> str:
        return self.access_token

    @computed_field(alias="refresh_token")  # type: ignore[prop-decorator]
    @property
    def refresh_token_snake(self) -> str | None:
        return self.refresh_token


class SignupRequest(CamelModel):
    """회원가입 요청 (프론트엔드 SignupPage.jsx 연동 계약)"""

    email: str = Field(..., min_length=1, max_length=255, description="이메일 주소")
    password: str = Field(
        ...,
        min_length=8,
        description="비밀번호 (8자 이상, 영문 대소문자/숫자/특수문자)",
    )
    nickname: str | None = Field(
        default=None,
        max_length=50,
        description="닉네임 (미지정 시 이메일 아이디 자동 사용)",
    )
    birth_date: str | None = Field(default=None, description="생년월일 (YYYY-MM-DD)")
    gender: str | None = Field(default=None, description="성별 (MALE, FEMALE)")
    agree_terms: bool = Field(..., description="서비스 이용약관 동의 여부 (필수)")
    agree_privacy: bool = Field(..., description="개인정보 처리방침 동의 여부 (필수)")
    agree_ai_analysis: bool = Field(
        default=False, description="AI 분석 활용 동의 여부 (선택)"
    )


class SignupResponse(CamelModel):
    """회원가입 응답 (201 Created)"""

    member_id: str
    email: str
    nickname: str
    message: str = "회원가입이 완료되었습니다."


class ConfirmSignupRequest(CamelModel):
    """회원가입 확인 / 이메일 인증 요청"""

    email: str = Field(..., min_length=1, description="인증 대상 이메일")
    code: str = Field(..., min_length=1, description="인증 코드")


class ResendSignupRequest(CamelModel):
    """회원가입 인증코드 재전송 요청"""

    email: str = Field(..., min_length=1, description="재전송 대상 이메일")
