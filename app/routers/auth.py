from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.db.session import get_db
from app.schemas.auth import (
    AvailabilityRequest,
    AvailabilityResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    SocialLoginRequest,
    TokenResponse,
)
from app.services.member_service import MemberService
from app.services.social_auth_service import SocialAuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """프론트엔드 새로고침 세션 복원을 위한 HttpOnly 쿠키를 설정합니다."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        path="/",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="개발 및 테스트용 이메일 로그인 (프론트엔드 호환)",
)
async def dev_login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    프론트엔드 로그인 화면 및 로컬 개발용 엔드포인트입니다.
    이메일로 회원을 조회하거나 신규 테스트 계정을 자동 생성(Get-or-Create)하고,
    기본 책장과 기본 대표 고양이 사서(CAT)를 자동 지급합니다.
    자체 Bearer JWT 및 HttpOnly 세션 쿠키를 동시에 발급합니다.
    """
    member, is_new = await MemberService.get_or_create_dev_member(db, req.email)

    access_token = create_access_token(member.member_id, member.email, member.nickname)
    refresh_token = create_refresh_token(member.member_id)

    _set_refresh_cookie(response, refresh_token)
    profile = MemberService.to_profile_response(member)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        member_id=str(member.member_id),
        is_new_member=is_new,
        member=profile,
    )


@router.post(
    "/social/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Google 소셜 로그인 및 자동 회원가입",
)
async def google_social_login(
    req: SocialLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    프론트엔드에서 수신한 Google ID Token을 검증하고, 회원을 생성하거나 조회하여 자체 JWT를 발급합니다.
    """
    social_info = await SocialAuthService.verify_google_token(req.token)
    member, is_new = await MemberService.get_or_create_social_member(
        db, social_info, req.agreed_terms_ids
    )

    access_token = create_access_token(member.member_id, member.email, member.nickname)
    refresh_token = create_refresh_token(member.member_id)

    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        member_id=str(member.member_id),
        is_new_member=is_new,
    )


@router.post(
    "/social/kakao",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Kakao 소셜 로그인 및 자동 회원가입",
)
async def kakao_social_login(
    req: SocialLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    프론트엔드에서 수신한 Kakao Access Token을 검증하고, 회원을 생성하거나 조회하여 자체 JWT를 발급합니다.
    """
    social_info = await SocialAuthService.verify_kakao_token(req.token)
    member, is_new = await MemberService.get_or_create_social_member(
        db, social_info, req.agreed_terms_ids
    )

    access_token = create_access_token(member.member_id, member.email, member.nickname)
    refresh_token = create_refresh_token(member.member_id)

    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        member_id=str(member.member_id),
        is_new_member=is_new,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="JWT 토큰 갱신",
)
async def refresh_token(
    response: Response,
    req: RefreshTokenRequest | None = None,
    cookie_token: str | None = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Refresh Token을 검증하고 새로운 Access Token 및 Refresh Token을 발급합니다.
    요청 Body 또는 HttpOnly Cookie 중 하나로 전달된 Refresh Token을 지원합니다.
    """
    token_str = (
        req.refresh_token if req and req.refresh_token else None
    ) or cookie_token
    if not token_str:
        raise UnauthorizedException("Refresh Token이 제공되지 않았습니다.")

    member_id = decode_refresh_token(token_str)
    member = await MemberService.get_member_by_id(db, member_id)

    new_access_token = create_access_token(
        member.member_id, member.email, member.nickname
    )
    new_refresh_token = create_refresh_token(member.member_id)

    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        member_id=str(member.member_id),
        is_new_member=False,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
)
async def logout(response: Response) -> None:
    """
    사용자 세션을 종료하고 로그아웃합니다 (멱등성 보장, 쿠키 삭제, 204 No Content).
    """
    response.delete_cookie(key="refresh_token", path="/")
    return None


@router.post(
    "/availability",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="이메일 또는 닉네임 중복 확인",
)
async def check_availability(
    req: AvailabilityRequest,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    """
    이메일 또는 닉네임이 사용 가능한지 확인합니다.
    """
    is_available, msg = await MemberService.check_availability(db, req.field, req.value)
    return AvailabilityResponse(
        field=req.field,
        value=req.value,
        is_available=is_available,
        message=msg,
    )
