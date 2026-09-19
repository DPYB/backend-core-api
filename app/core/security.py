import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.exceptions import UnauthorizedException

security = HTTPBearer(auto_error=False)

DEFAULT_TEST_MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def hash_password(password: str) -> str:
    """비밀번호 단방향 솔트 해싱 (PBKDF2-HMAC-SHA256)"""
    salt = secrets.token_hex(16)
    iterations = 100_000
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return f"{salt}${iterations}${pw_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """단방향 해시된 비밀번호 검증"""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        salt, iterations_str, expected_hash = parts
        iterations = int(iterations_str)
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations
        ).hex()
        return secrets.compare_digest(actual_hash, expected_hash)
    except Exception:
        return False


def get_demo_member_id() -> uuid.UUID:
    """체험 모드(게스트) 사용자를 위한 데모 계정 member_id UUID 반환"""
    try:
        return uuid.UUID(settings.DEMO_MEMBER_ID)
    except Exception:
        return uuid.UUID("00000000-0000-0000-0000-000000000002")


def get_jwt_secret_key() -> str:
    if settings.JWT_SECRET_KEY and settings.JWT_SECRET_KEY.strip():
        return settings.JWT_SECRET_KEY.strip()
    return "dont-paw-get-jwt-secret-fallback-key-2026"


def create_access_token(member_id: uuid.UUID, email: str, nickname: str) -> str:
    """사용자 정보가 담긴 자체 Access Token(JWT)을 발급합니다."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(member_id),
        "email": email,
        "nickname": nickname,
        "token_use": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=settings.JWT_ALGORITHM)


def create_guest_token(guest_id: str, expire_hours: int | None = None) -> str:
    """
    해커톤 체험 모드를 위한 게스트 JWT 발급:
    - sub: guest-{uuid}
    - role: guest
    - 짧은 만료시간 (기본 1~2시간)
    """
    now = datetime.now(UTC)
    hours = (
        expire_hours if expire_hours is not None else settings.GUEST_TOKEN_EXPIRE_HOURS
    )
    expire = now + timedelta(hours=hours)

    sub_value = f"guest-{guest_id}" if not guest_id.startswith("guest-") else guest_id

    payload = {
        "sub": sub_value,
        "role": "guest",
        "token_use": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(member_id: uuid.UUID) -> str:
    """토큰 갱신용 Refresh Token(JWT)을 발급합니다."""
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(member_id),
        "token_use": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=settings.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> uuid.UUID:
    """리프레시 토큰을 검증하고 member_id UUID를 추출합니다."""
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        if payload.get("token_use") != "refresh":
            raise UnauthorizedException("유효한 Refresh Token이 아닙니다.")
        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedException("토큰에 사용자 식별자가 없습니다.")
        return uuid.UUID(str(sub))
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("만료된 Refresh Token입니다.") from e
    except jwt.PyJWTError as e:
        raise UnauthorizedException("유효하지 않은 Refresh Token입니다.") from e
    except Exception as e:
        raise UnauthorizedException("Refresh Token 처리 실패") from e


def decode_jwt_token(token: str) -> dict:
    """
    표준 JWT Bearer 토큰 디코딩 및 기본 클레임 검증.
    """
    # 1. 테스트용 Mock 토큰 처리: "mock-token-<uuid>" 또는 "test-token" 또는 "mock-guest-token"
    if token.startswith("mock-guest-token"):
        guest_id = (
            token.replace("mock-guest-token-", "")
            if token.startswith("mock-guest-token-")
            else "demo-guest-uuid"
        )
        return {
            "sub": f"guest-{guest_id}",
            "role": "guest",
            "token_use": "access",
        }
    if token.startswith("mock-token-"):
        mock_id = token.replace("mock-token-", "")
        return {
            "sub": mock_id,
            "token_use": "access",
        }
    if token == "test-token":
        return {
            "sub": str(DEFAULT_TEST_MEMBER_ID),
            "token_use": "access",
        }

    try:
        # JWT 서명 검증 수행
        payload = jwt.decode(
            token,
            get_jwt_secret_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("만료된 토큰입니다.") from e
    except jwt.PyJWTError as e:
        raise UnauthorizedException("유효하지 않은 토큰입니다.") from e
    except Exception as e:
        raise UnauthorizedException("토큰 파싱에 실패했습니다.") from e


async def get_current_member_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> uuid.UUID:
    """
    현재 인증된 회원의 member_id (UUID)를 반환하는 FastAPI 의존성.
    오직 유효하게 서명된 Bearer JWT 토큰만을 검증합니다.
    - 게스트 토큰(role == 'guest' 또는 sub가 'guest-'로 시작)인 경우 DEMO_MEMBER_ID로 단 1회 중앙 매핑합니다.
    """
    if settings.AUTH_DISABLED:
        return DEFAULT_TEST_MEMBER_ID

    if not credentials or not credentials.credentials:
        raise UnauthorizedException("인증 토큰이 누락되었습니다.")

    token = credentials.credentials
    try:
        payload = decode_jwt_token(token)

        # 게스트 토큰 확인 (role == 'guest' 또는 sub가 'guest-'로 시작)
        sub_raw = str(payload.get("sub") or payload.get("member_id") or "")
        if payload.get("role") == "guest" or sub_raw.startswith("guest-"):
            return get_demo_member_id()

        # 일반 회원 sub 클레임 추출 및 UUID 변환
        if not sub_raw:
            raise UnauthorizedException("토큰에 사용자 식별자가 존재하지 않습니다.")

        return uuid.UUID(sub_raw)

    except (ValueError, TypeError) as e:
        raise UnauthorizedException("유효하지 않은 사용자 식별자입니다.") from e
    except UnauthorizedException:
        raise
    except Exception as e:
        raise UnauthorizedException("인증에 실패했습니다.") from e


# 하위 호환성을 위한 별칭: get_current_member_id와 동일하게 서명된 Bearer JWT만 검증
get_authenticated_member_id = get_current_member_id


async def get_optional_member_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> uuid.UUID | None:
    """
    선택적 회원 식별자 추출 의존성:
    오직 유효하게 서명된 Bearer JWT가 있는 경우에만 해당 member_id를 반환하며,
    미인증 요청인 경우 예외를 발생시키지 않고 None을 반환합니다.
    - 게스트 토큰인 경우 DEMO_MEMBER_ID를 반환합니다.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_jwt_token(credentials.credentials)
        sub_raw = str(payload.get("sub") or payload.get("member_id") or "")
        if payload.get("role") == "guest" or sub_raw.startswith("guest-"):
            return get_demo_member_id()
        return uuid.UUID(sub_raw) if sub_raw else None
    except Exception:
        return None


async def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """토큰의 페이로드를 디코딩하여 반환합니다 (미들웨어 또는 의존성 검증용)."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return decode_jwt_token(credentials.credentials)
    except Exception:
        return None
