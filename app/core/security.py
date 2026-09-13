import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.exceptions import UnauthorizedException

security = HTTPBearer(auto_error=False)

DEFAULT_TEST_MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def decode_jwt_token(token: str) -> dict:
    """
    표준 JWT Bearer 토큰 디코딩 및 기본 클레임 검증.
    """
    # 1. 테스트용 Mock 토큰 처리: "mock-token-<uuid>" 또는 "test-token"
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
        # JWT_SECRET_KEY가 구성되어 있으면 서명 검증 수행, 없으면 페이로드 디코딩
        if settings.JWT_SECRET_KEY:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )
        else:
            payload = jwt.decode(
                token, options={"verify_signature": False, "verify_aud": False}
            )
        return payload
    except jwt.PyJWTError as e:
        raise UnauthorizedException("유효하지 않은 토큰입니다.") from e
    except Exception as e:
        raise UnauthorizedException("토큰 파싱에 실패했습니다.") from e


async def get_current_member_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> uuid.UUID:
    """
    현재 인증된 회원의 member_id (UUID)를 반환하는 FastAPI 의존성.
    """
    if settings.AUTH_DISABLED:
        return DEFAULT_TEST_MEMBER_ID

    if not credentials or not credentials.credentials:
        raise UnauthorizedException("인증 토큰이 누락되었습니다.")

    token = credentials.credentials
    try:
        payload = decode_jwt_token(token)

        # sub 클레임 추출 및 UUID 변환 (사용자 고유 UUID 식별자)
        sub = payload.get("sub") or payload.get("member_id")
        if not sub:
            raise UnauthorizedException("토큰에 사용자 식별자가 존재하지 않습니다.")

        return uuid.UUID(str(sub))

    except (ValueError, TypeError) as e:
        raise UnauthorizedException("유효하지 않은 사용자 식별자입니다.") from e
    except UnauthorizedException:
        raise
    except Exception as e:
        raise UnauthorizedException("인증에 실패했습니다.") from e
