import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


@dataclass
class SocialUserInfo:
    provider: str
    provider_id: str
    email: str
    nickname: str
    profile_image_url: str | None = None


class SocialAuthService:
    @staticmethod
    async def verify_google_token(id_token: str) -> SocialUserInfo:
        """
        Google ID Token을 Google 공식 tokeninfo 엔드포인트로 검증하고 사용자 프로필을 반환합니다.
        """
        if not id_token or not id_token.strip():
            raise AppException(
                401, "INVALID_TOKEN", "Google id_token이 제공되지 않았습니다."
            )

        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token.strip()}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
        except Exception as e:
            logger.error("Google tokeninfo request failed: %s", e)
            raise AppException(
                502,
                "AUTHENTICATION_FAILED",
                "Google 인증 서버 통신 중 오류가 발생했습니다.",
            )

        if resp.status_code != 200:
            logger.warning(
                "Invalid Google token: status=%s, body=%s", resp.status_code, resp.text
            )
            raise AppException(
                401, "INVALID_TOKEN", "유효하지 않거나 만료된 Google ID 토큰입니다."
            )

        data = resp.json()

        # GOOGLE_CLIENT_ID가 설정되어 있는 경우 audience 검증
        if settings.GOOGLE_CLIENT_ID and data.get("aud") != settings.GOOGLE_CLIENT_ID:
            logger.warning(
                "Google token aud mismatch: expected=%s, actual=%s",
                settings.GOOGLE_CLIENT_ID,
                data.get("aud"),
            )
            raise AppException(
                401, "INVALID_TOKEN", "Google 클라이언트 ID가 일치하지 않습니다."
            )

        provider_id = data.get("sub")
        email = data.get("email")
        if not provider_id or not email:
            raise AppException(
                401, "INVALID_TOKEN", "Google 프로필에서 필수 정보를 찾을 수 없습니다."
            )

        nickname = data.get("name") or email.split("@")[0]
        picture = data.get("picture")

        return SocialUserInfo(
            provider="GOOGLE",
            provider_id=provider_id,
            email=email,
            nickname=nickname,
            profile_image_url=picture,
        )

    @staticmethod
    async def verify_kakao_token(access_token: str) -> SocialUserInfo:
        """
        Kakao Access Token을 Kakao 사용자 정보 API로 검증하고 사용자 프로필을 반환합니다.
        """
        if not access_token or not access_token.strip():
            raise AppException(
                401, "INVALID_TOKEN", "Kakao access_token이 제공되지 않았습니다."
            )

        url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token.strip()}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
        except Exception as e:
            logger.error("Kakao user/me request failed: %s", e)
            raise AppException(
                502,
                "AUTHENTICATION_FAILED",
                "Kakao 인증 서버 통신 중 오류가 발생했습니다.",
            )

        if resp.status_code != 200:
            logger.warning(
                "Invalid Kakao token: status=%s, body=%s", resp.status_code, resp.text
            )
            raise AppException(
                401, "INVALID_TOKEN", "유효하지 않거나 만료된 Kakao 액세스 토큰입니다."
            )

        data = resp.json()
        kakao_id = data.get("id")
        if not kakao_id:
            raise AppException(
                401, "INVALID_TOKEN", "Kakao 응답에서 사용자 ID를 찾을 수 없습니다."
            )

        provider_id = str(kakao_id)
        kakao_account = data.get("kakao_account") or {}
        profile = kakao_account.get("profile") or {}

        email = kakao_account.get("email") or f"kakao_{provider_id}@dontpawget.app"
        nickname = profile.get("nickname") or f"카카오유저_{provider_id[:6]}"
        picture = profile.get("profile_image_url")

        return SocialUserInfo(
            provider="KAKAO",
            provider_id=provider_id,
            email=email,
            nickname=nickname,
            profile_image_url=picture,
        )
