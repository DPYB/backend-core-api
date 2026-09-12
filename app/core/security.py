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
    Cognito Access Token 디코딩 및 기본 클레임 검증.
    """
    # 1. 테스트용 Mock 토큰 처리: "mock-token-<uuid>" 또는 "test-token"
    if token.startswith("mock-token-"):
        mock_id = token.replace("mock-token-", "")
        return {
            "sub": mock_id,
            "token_use": "access",
            "client_id": settings.AUTH_APP_CLIENT_ID,
        }
    if token == "test-token":
        return {
            "sub": str(DEFAULT_TEST_MEMBER_ID),
            "token_use": "access",
            "client_id": settings.AUTH_APP_CLIENT_ID,
        }

    try:
        # 서명 검증 없이 unverified decode로 claims를 파싱 (Cognito 공개키/JWKS 필요 시 확장 가능)
        payload = jwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        return payload
    except Exception as e:
        raise UnauthorizedException("유효하지 않은 토큰입니다.") from e


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

        # 1. token_use 검증 (ID 토큰 불가, 반드시 access 토큰이어야 함)
        if payload.get("token_use") != "access":
            raise UnauthorizedException("유효하지 않은 토큰입니다.")

        # 2. client_id 일치 여부 확인 (설정된 경우에만)
        if settings.AUTH_APP_CLIENT_ID:
            token_client_id = payload.get("client_id")
            if token_client_id and token_client_id != settings.AUTH_APP_CLIENT_ID:
                raise UnauthorizedException("권한이 없는 클라이언트 토큰입니다.")

        # 3. sub 클레임 추출 및 UUID 변환
        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedException("토큰에 사용자 식별자가 존재하지 않습니다.")

        return uuid.UUID(sub)

    except (ValueError, TypeError, KeyError) as e:
        raise UnauthorizedException("유효하지 않은 사용자 식별자입니다.") from e
    except UnauthorizedException:
        raise
    except Exception as e:
        raise UnauthorizedException("인증에 실패했습니다.") from e
