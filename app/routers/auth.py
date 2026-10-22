import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppException, UnauthorizedException
from app.core.rate_limit import (
    auth_rate_limiter,
    get_client_ip,
    guest_rate_limiter,
)
from app.core.security import (
    create_access_token,
    create_guest_token,
    create_refresh_token,
    decode_refresh_token,
    get_authenticated_member_id,
    verify_password,
)
from app.db.session import get_db
from app.models.member import EmailVerification, Member
from app.schemas.auth import (
    AvailabilityRequest,
    AvailabilityResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    ConfirmSignupRequest,
    GuestLoginRequest,
    GuestLoginResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    ResendSignupRequest,
    SignupRequest,
    SignupResponse,
    SocialLoginRequest,
    TokenResponse,
)
from app.services.email_service import EmailService
from app.services.member_service import MemberService
from app.services.social_auth_service import SocialAuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """프론트엔드 새로고침 세션 복원을 위한 HttpOnly 쿠키를 설정합니다."""
    # 프로덕션 또는 스테이징 등 HTTPS 크로스 도메인 환경에서는 SameSite=None, Secure=True 필수
    is_production = settings.ENV in ("production", "staging")
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="none" if is_production else "lax",
        secure=is_production,
        path="/",
    )


@router.post(
    "/guest",
    response_model=GuestLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="게스트 체험 토큰 발급 및 세션 연장",
)
async def issue_guest_token(
    request: Request,
    response: Response,
    req: GuestLoginRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> GuestLoginResponse:
    """
    해커톤 심사 및 체험 모드용 게스트 JWT 발급/연장:
    - sub: guest-{uuid}, role: guest
    - 세션 유지: guest_id가 들어오면 기존 UUID를 유지하며 만료시간만 연장
    - Rate Limit 분리: 신규 발급은 분당 5회(빡빡함), 갱신(guest_id 보유)은 분당 60회(널널함)
    - 데모 회원 레코드 사전 보장
    """
    client_ip = get_client_ip(request)
    guest_id_raw = (
        req.guest_id.strip() if req and req.guest_id and req.guest_id.strip() else None
    )

    if guest_id_raw:
        # [갱신/세션 연장] 널널한 IP 제한 (분당 60회)
        guest_rate_limiter.check(
            f"guest_refresh:{client_ip}", max_requests=60, window_seconds=60
        )
        # 만약 'guest-' 접두사가 이미 붙어 있다면 UUID 부분만 추출하여 정규화
        clean_guest_id = guest_id_raw.replace("guest-", "")
    else:
        # [신규 발급] 빡빡한 IP 제한 (분당 5회)
        guest_rate_limiter.check(
            f"guest_issue:{client_ip}", max_requests=5, window_seconds=60
        )
        clean_guest_id = str(uuid.uuid4())

    # 공용 게스트 회원(기본책장, 대표사서, 초기 시드 9권 등) 존재 보장
    await MemberService.ensure_guest_member(db)

    # 게스트 JWT 생성 (1~2시간 만료)
    access_token = create_guest_token(clean_guest_id)
    expires_in = settings.GUEST_TOKEN_EXPIRE_HOURS * 3600
    sub_val = f"guest-{clean_guest_id}"

    return GuestLoginResponse(
        access_token=access_token,
        refresh_token=None,
        token_type="Bearer",
        expires_in=expires_in,
        guest_id=clean_guest_id,
        sub=sub_val,
        role="guest",
        is_guest=True,
    )


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
async def signup_member(
    request: Request,
    req: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> SignupResponse:
    """
    정식 회원가입 엔드포인트:
    - IP당 분당 5회 Rate Limit 검증 (429 Too Many Requests)
    - 이메일당 24시간 5회 발송 상한 및 전체 400통 모니터링 검증
    - 이메일 중복 확인 (이미 존재 시 409 Conflict)
    - 필수 약관 동의 검증 (미동의 시 400 Bad Request)
    - 신규 회원 레코드 생성 및 비밀번호 단방향 해싱 저장
    - 동시 가입 시 DB 충돌(IntegrityError) 발생 시 db.rollback() 후 409 Conflict 반환
    - 기본 책장(Default Shelf) 및 기본 대표 고양이 사서(CAT "블루", Lv.1) 자동 지급
    - 약관 동의 이력 영속화
    - 201 Created 반환
    """
    client_ip = get_client_ip(request)
    auth_rate_limiter.check(f"signup:{client_ip}", max_requests=5, window_seconds=60)

    member = await MemberService.register_member(db, req)
    return SignupResponse(
        member_id=str(member.member_id),
        email=member.email,
        nickname=member.nickname,
        message="회원가입이 완료되었습니다.",
    )


@router.post(
    "/signup/confirm",
    status_code=status.HTTP_200_OK,
    summary="회원가입 인증 확인 (이메일 인증 단계)",
)
async def confirm_signup(
    request: Request,
    req: ConfirmSignupRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    프론트엔드 이메일 인증(EmailVerification) 확인 엔드포인트:
    - IP당 분당 10회 Rate Limit 검증 (대입 공격 1차 차단)
    - 회원 존재 여부 검증
    - 최신 미인증 인증 코드 조회 시 with_for_update() 행 잠금 (동시성 안전성)
    - 시도 횟수(failed_attempts >= 5) 최우선 차단
    - 인증 코드 불일치 시 failed_attempts += 1 원자적 갱신
      (5회 도달 시 expires_at = now - 1s로 즉시 덮어써서 물리적 만료 처리)
    - 인증 완료 시 회원 status를 ACTIVE로 변경
    """
    client_ip = get_client_ip(request)
    auth_rate_limiter.check(
        f"signup_confirm:{client_ip}", max_requests=10, window_seconds=60
    )

    clean_email = req.email.strip().lower()
    stmt = select(Member).where(
        Member.email == clean_email,
        Member.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    member = res.scalars().first()
    if not member:
        raise AppException(404, "MEMBER_NOT_FOUND", "가입되지 않은 이메일입니다.")

    if member.status == "ACTIVE":
        return {"message": "이메일 인증이 완료되었습니다.", "status": "ACTIVE"}

    # 최신 미인증 코드 조회 (행 잠금으로 동시 요청 직렬화)
    stmt_v = (
        select(EmailVerification)
        .where(
            EmailVerification.email == clean_email,
            EmailVerification.is_verified.is_(False),
        )
        .order_by(EmailVerification.id.desc())
        .with_for_update()
    )
    res_v = await db.execute(stmt_v)
    verification = res_v.scalars().first()

    if not verification:
        raise AppException(
            400,
            "INVALID_VERIFICATION_CODE",
            "인증 코드가 존재하지 않거나 만료되었습니다.",
        )

    # 1. 시도 횟수 초과 여부 최우선 검증
    if verification.failed_attempts >= 5:
        raise AppException(
            400,
            "VERIFICATION_ATTEMPTS_EXCEEDED",
            "인증 번호 입력 가능 횟수(5회)를 초과하여 해당 코드가 만료되었습니다. 인증 번호를 다시 요청해 주세요.",
        )

    # 2. 만료 시간 검증
    now = datetime.now(UTC)
    expires_at = (
        verification.expires_at
        if verification.expires_at.tzinfo is not None
        else verification.expires_at.replace(tzinfo=UTC)
    )
    if expires_at < now:
        raise AppException(
            400,
            "VERIFICATION_CODE_EXPIRED",
            "인증 코드가 만료되었습니다. 인증 코드를 다시 요청해 주세요.",
        )

    # 3. 인증 코드 일치 여부 확인
    if verification.code.strip() != req.code.strip():
        verification.failed_attempts += 1
        if verification.failed_attempts >= 5:
            # 5회 도달 시 즉시 만료 처리 (시간을 과거로 되돌려 물리적 만료)
            verification.expires_at = now - timedelta(seconds=1)
            await db.commit()
            raise AppException(
                400,
                "VERIFICATION_ATTEMPTS_EXCEEDED",
                "인증 번호 입력 가능 횟수(5회)를 초과하여 해당 코드가 만료되었습니다. 인증 번호를 다시 요청해 주세요.",
            )
        await db.commit()
        raise AppException(
            400,
            "INVALID_VERIFICATION_CODE",
            f"인증 코드가 올바르지 않습니다. (남은 시도: {5 - verification.failed_attempts}회)",
        )

    verification.is_verified = True
    member.status = "ACTIVE"
    await db.commit()

    return {"message": "이메일 인증이 완료되었습니다.", "status": "ACTIVE"}


@router.post(
    "/signup/resend",
    status_code=status.HTTP_200_OK,
    summary="회원가입 인증코드 재전송",
)
async def resend_signup_code(
    request: Request,
    req: ResendSignupRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    회원가입 인증코드 재전송:
    - IP당 분당 3회 Rate Limit 검증 (429 Too Many Requests)
    - 회원 행 with_for_update() 잠금으로 동시성 안전성 보장
    - 30초 내 재발송 쿨다운 확인
    - 이메일당 24시간 5회 발송 상한 및 전체 400통 모니터링 검증
    - 새 6자리 난수 코드 레코드 생성 후 즉시 commit(락 해제)
    - 트랜잭션 밖에서 Gmail SMTP 재발송 (DB 락 점유 방지)
    """
    client_ip = get_client_ip(request)
    auth_rate_limiter.check(
        f"signup_resend:{client_ip}", max_requests=3, window_seconds=60
    )

    clean_email = req.email.strip().lower()
    stmt = (
        select(Member)
        .where(
            Member.email == clean_email,
            Member.deleted_at.is_(None),
        )
        .with_for_update()
    )
    res = await db.execute(stmt)
    member = res.scalars().first()
    if not member:
        raise AppException(404, "MEMBER_NOT_FOUND", "가입되지 않은 이메일입니다.")

    if member.status == "ACTIVE":
        return {"message": "이미 이메일 인증이 완료된 계정입니다."}

    # 최근 발송 30초 쿨다운
    stmt_v = (
        select(EmailVerification)
        .where(EmailVerification.email == clean_email)
        .order_by(EmailVerification.id.desc())
    )
    res_v = await db.execute(stmt_v)
    latest_v = res_v.scalars().first()
    now = datetime.now(UTC)
    if latest_v:
        created_at = (
            latest_v.created_at
            if latest_v.created_at.tzinfo is not None
            else latest_v.created_at.replace(tzinfo=UTC)
        )
        if (now - created_at).total_seconds() < 30:
            raise AppException(
                429,
                "RATE_LIMIT_EXCEEDED",
                "인증 코드가 이미 발송되었습니다. 30초 후 다시 시도해 주세요.",
            )

    # 24시간 발송 쿼터 검증 (이메일당 5회 & 전체 400통 모니터링)
    await EmailService.check_email_quota(db, clean_email)

    code = EmailService.generate_verification_code()
    expires_at = now + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES)
    db.add(
        EmailVerification(
            email=clean_email,
            code=code,
            expires_at=expires_at,
            is_verified=False,
            failed_attempts=0,
        )
    )
    await db.commit()

    # 트랜잭션 밖에서 외부 SMTP 발송 (DB 락 점유 방지)
    await EmailService.send_verification_email(clean_email, code)
    return {"message": "인증 코드가 재전송되었습니다."}


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="개발 및 테스트용 이메일 로그인 (프론트엔드 호환)",
)
async def dev_login(
    request: Request,
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    프론트엔드 로그인 화면 및 로컬 개발용 엔드포인트입니다.
    - IP당 분당 10회 및 이메일당 분당 5회 Rate Limit 검증 (429 Too Many Requests)
    - 미인증 회원(PENDING_VERIFICATION)의 경우 403 EMAIL_NOT_VERIFIED 반환
    - 비밀번호 등록 회원의 경우 비밀번호 검증 (불일치 시 401)
    - 자체 Bearer JWT 및 HttpOnly 세션 쿠키 발급
    """
    client_ip = get_client_ip(request)
    clean_email = req.email.strip().lower()

    # 무차별 대입(Brute-force) 방어: IP당 10회, 이메일당 5회
    auth_rate_limiter.check(f"login_ip:{client_ip}", max_requests=10, window_seconds=60)
    auth_rate_limiter.check(
        f"login_email:{clean_email}", max_requests=5, window_seconds=60
    )
    stmt = select(Member).where(
        Member.email == clean_email,
        Member.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    existing_member = res.scalars().first()

    if not existing_member:
        raise AppException(404, "MEMBER_NOT_FOUND", "가입되지 않은 이메일입니다.")

    if existing_member.status == "PENDING_VERIFICATION":
        raise AppException(
            403,
            "EMAIL_NOT_VERIFIED",
            "이메일 인증이 완료되지 않았습니다. 메일함의 인증 코드를 확인해 주세요.",
        )
    if existing_member.password_hash and req.password:
        if not verify_password(req.password, existing_member.password_hash):
            raise AppException(
                401,
                "INVALID_CREDENTIALS",
                "이메일 또는 비밀번호가 올바르지 않습니다.",
            )
    member = existing_member
    is_new = False

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
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Google 소셜 로그인 및 자동 회원가입",
)
async def google_social_login(
    req: SocialLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
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
    "/social/kakao",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Kakao 소셜 로그인 및 자동 회원가입",
)
async def kakao_social_login(
    req: SocialLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
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
    is_production = settings.ENV in ("production", "staging")
    response.delete_cookie(
        key="refresh_token",
        path="/",
        samesite="none" if is_production else "lax",
        secure=is_production,
    )
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


@router.post(
    "/password/change",
    response_model=ChangePasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="로그인 회원 비밀번호 변경",
)
async def change_password(
    request: Request,
    req: ChangePasswordRequest,
    member_id: uuid.UUID = Depends(get_authenticated_member_id),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    """
    로그인된 회원의 비밀번호를 변경합니다.
    - IP당 분당 5회 및 회원당 분당 5회 Rate Limit 검증 (429 Too Many Requests)
    - 현재 비밀번호 검증 (불일치 시 401 Unauthorized)
    - 동일 비밀번호 거부 (400 Bad Request)
    - 복잡도 정책: 8자 이상, 영문 대/소문자, 숫자, 특수문자 포함 (400 Bad Request)
    """
    client_ip = get_client_ip(request)
    auth_rate_limiter.check(
        f"pwd_change_ip:{client_ip}", max_requests=5, window_seconds=60
    )
    auth_rate_limiter.check(
        f"pwd_change_member:{member_id}", max_requests=5, window_seconds=60
    )

    await MemberService.change_password(
        db, member_id, req.current_password, req.new_password
    )
    return ChangePasswordResponse()
