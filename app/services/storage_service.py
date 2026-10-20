import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings
from app.core.exceptions import (
    ImageNotFoundException,
    ImageStorageAccessDeniedException,
    InvalidImageUploadException,
)

logger = logging.getLogger(__name__)

# 허용 MIME 타입 및 확장자 매핑 SSOT
ALLOWED_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/webp": "webp",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
}

# 최대 허용 이미지 크기: 5MB
MAX_IMAGE_SIZE_BYTES: int = 5 * 1024 * 1024

# Presigned URL 유효 기간 (10분)
PRESIGNED_URL_EXPIRES_SECONDS: int = 600


class StorageService:
    """Cloudflare R2 (S3 호환) 객체 스토리지 전담 서비스"""

    _s3_client: Any = None

    @classmethod
    def get_s3_client(cls) -> Any:
        """boto3 S3 클라이언트 팩토리 (싱글톤 재사용)"""
        if cls._s3_client is not None:
            return cls._s3_client

        if (
            not settings.R2_ACCOUNT_ID
            or not settings.R2_ACCESS_KEY_ID
            or not settings.R2_SECRET_ACCESS_KEY
        ):
            raise InvalidImageUploadException(
                "Cloudflare R2 스토리지 자격 증명이 설정되지 않았습니다."
            )

        endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        cls._s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        return cls._s3_client

    @classmethod
    def _validate_content_type(cls, content_type: str) -> str:
        """Content-Type 유효성 검증 및 해당 파일 확장자 반환"""
        clean_content_type = (content_type or "").strip().lower()
        if clean_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            allowed_list = list(ALLOWED_IMAGE_CONTENT_TYPES.keys())
            raise InvalidImageUploadException(
                f"지원하지 않는 이미지 형식입니다: '{content_type}'. "
                f"지원되는 형식: {', '.join(allowed_list)}"
            )
        return ALLOWED_IMAGE_CONTENT_TYPES[clean_content_type]

    @classmethod
    def generate_storage_key(
        cls,
        category: str,
        member_id: uuid.UUID,
        ext: str,
    ) -> str:
        """
        고유 객체 키 생성 규칙:
        {category}/{env}/{member_id}_{timestamp}_{uuid8}.{ext}
        """
        timestamp = int(datetime.now(UTC).timestamp())
        random_suffix = uuid.uuid4().hex[:8]
        env_prefix = settings.R2_ENV_PREFIX or settings.ENV
        return f"{category}/{env_prefix}/{member_id}_{timestamp}_{random_suffix}.{ext}"

    @classmethod
    def _generate_presigned_url(
        cls,
        category: str,
        category_name: str,
        member_id: uuid.UUID,
        content_type: str = "image/webp",
    ) -> dict[str, Any]:
        """Presigned PUT URL 및 최종 CDN URL을 생성하는 내부 공통 헬퍼"""
        clean_content_type = (content_type or "").strip().lower()
        ext = cls._validate_content_type(clean_content_type)
        key = cls.generate_storage_key(
            category=category,
            member_id=member_id,
            ext=ext,
        )

        s3 = cls.get_s3_client()
        params = {
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
            "ContentType": clean_content_type,
        }

        presigned_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=PRESIGNED_URL_EXPIRES_SECONDS,
        )

        cdn_prefix = settings.R2_PUBLIC_URL_PREFIX.rstrip("/")
        image_url = f"{cdn_prefix}/{key}"

        # 로그에는 서명 파라미터를 제외한 순수 경로만 안전하게 기록
        masked_url = (
            presigned_url.split("?")[0] if "?" in presigned_url else presigned_url
        )
        logger.info(
            "Generated %s image presigned URL for member=%s, key=%s, target=%s",
            category_name,
            member_id,
            key,
            masked_url,
        )

        return {
            "presigned_url": presigned_url,
            "image_url": image_url,
            "expires_in": PRESIGNED_URL_EXPIRES_SECONDS,
        }

    @classmethod
    def generate_profile_image_presigned_url(
        cls,
        member_id: uuid.UUID,
        content_type: str = "image/webp",
    ) -> dict[str, Any]:
        """
        프로필 사진 업로드용 Presigned PUT URL 및 최종 CDN URL을 생성합니다.
        보안상 Presigned URL 로깅 시 쿼리 파라미터(서명 토큰)를 마스킹합니다.
        """
        return cls._generate_presigned_url(
            category="profile",
            category_name="profile",
            member_id=member_id,
            content_type=content_type,
        )

    @classmethod
    def generate_scrap_image_presigned_url(
        cls,
        member_id: uuid.UUID,
        content_type: str = "image/webp",
    ) -> dict[str, Any]:
        """
        스크랩(문장 수집) 이미지 업로드용 Presigned PUT URL 및 최종 CDN URL을 생성합니다.
        보안상 Presigned URL 로깅 시 쿼리 파라미터(서명 토큰)를 마스킹합니다.
        """
        return cls._generate_presigned_url(
            category="quote",
            category_name="scrap",
            member_id=member_id,
            content_type=content_type,
        )

    @classmethod
    def _verify_uploaded_image(
        cls,
        member_id: uuid.UUID,
        image_url: str | None,
        category: str,
        category_name: str,
    ) -> None:
        """
        업로드 완료된 이미지 URL의 무결성을 검증하는 내부 공통 헬퍼:
        1. R2 커스텀 CDN URL이 아닌 경우 (프론트 정적 이미지, Base64 Data URL, 외부 소셜 URL 등) 허용 통과
        2. R2 CDN URL인 경우:
           - 카테고리 저장 경로 검증
           - 본인이 발급받은 키인지 검증 (타인 키 도용 차단)
           - R2 스토리지에 실제 업로드 완료된 객체인지 확인 (head_object)
           - 용량 상한 (5MB) 및 Content-Type 검증
           - 매직 바이트(바이너리 시그니처) 검증 및 불량 객체 자동 삭제
        """
        if not image_url or not image_url.strip():
            return

        clean_url = image_url.strip()
        cdn_prefix = settings.R2_PUBLIC_URL_PREFIX.rstrip("/")

        # R2 커스텀 도메인 이미지가 아니면 검증 통과 (예: /profile/clia.png, Base64, 외부 소셜 URL)
        if not clean_url.startswith(cdn_prefix):
            return

        # S3 객체 키 추출
        key = clean_url[len(cdn_prefix) :].lstrip("/")
        if not key:
            raise InvalidImageUploadException("올바른 이미지 경로가 아닙니다.")

        # 키 형식 검증: category/env/{member_id}_{timestamp}_{uuid}.{ext}
        parts = key.split("/")
        if len(parts) < 3 or parts[0] != category:
            raise InvalidImageUploadException(
                f"{category_name} 이미지 저장 경로가 올바르지 않습니다."
            )

        filename = parts[-1]
        expected_prefix = f"{member_id}_"
        if not filename.startswith(expected_prefix):
            logger.warning(
                "Access denied: Member %s attempted to use image key owned by someone else: %s",
                member_id,
                key,
            )
            raise ImageStorageAccessDeniedException(
                f"본인이 업로드한 {category_name} 이미지만 등록할 수 있습니다."
            )

        # R2 실제 객체 존재 여부 및 메타데이터 확인
        s3 = cls.get_s3_client()
        try:
            head_res = s3.head_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code in ("404", "NoSuchKey") or status_code == 404:
                raise ImageNotFoundException(
                    "스토리지에 업로드되지 않은 이미지입니다. 먼저 파일 업로드를 완료해 주세요."
                ) from e
            logger.error("Failed to check image object in R2: %s", str(e))
            raise InvalidImageUploadException(
                "이미지 확인 중 오류가 발생했습니다."
            ) from e

        # 용량 상한 검증 (5MB)
        content_length = head_res.get("ContentLength", 0)
        if content_length > MAX_IMAGE_SIZE_BYTES or content_length <= 0:
            cls._safe_delete_object(key)
            raise InvalidImageUploadException(
                f"이미지 파일 크기가 유효하지 않거나 최대 허용치(5MB)를 초과합니다. (크기: {content_length} bytes)"
            )

        # Content-Type 헤더 검증
        obj_content_type = head_res.get("ContentType", "").lower()
        if obj_content_type and obj_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            cls._safe_delete_object(key)
            raise InvalidImageUploadException(
                f"허용되지 않은 이미지 형식입니다: {obj_content_type}"
            )

        # 실제 이미지 바이너리 헤더(매직 넘버) 검증 (앞 16바이트)
        try:
            get_res = s3.get_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
                Range="bytes=0-15",
            )
            header_bytes = get_res["Body"].read()
        except Exception as e:
            logger.error("Failed to read image header bytes: %s", str(e))
            raise InvalidImageUploadException(
                "이미지 파일 바이너리를 확인할 수 없습니다."
            ) from e

        detected_ext = cls._detect_image_format_from_bytes(header_bytes)
        if not detected_ext:
            cls._safe_delete_object(key)
            raise InvalidImageUploadException(
                "업로드된 파일이 유효한 이미지(WebP, JPEG, PNG, GIF) 형식이 아닙니다."
            )

    @classmethod
    def verify_uploaded_profile_image(
        cls,
        member_id: uuid.UUID,
        image_url: str | None,
    ) -> None:
        """
        프로필 갱신 전 이미지 URL의 무결성을 검증합니다.
        1. R2 커스텀 CDN URL이 아닌 경우 (프론트 정적 이미지, 소셜 이미지 등) 허용 통과
        2. R2 CDN URL인 경우:
           - 본인이 발급받은 키인지 검증 (타인 키 도용 차단)
           - R2 스토리지에 실제 업로드 완료된 객체인지 확인 (head_object)
           - 용량 상한 (5MB) 및 Content-Type 검증
        """
        cls._verify_uploaded_image(
            member_id=member_id,
            image_url=image_url,
            category="profile",
            category_name="프로필",
        )

    @classmethod
    def verify_uploaded_scrap_image(
        cls,
        member_id: uuid.UUID,
        image_url: str | None,
    ) -> None:
        """
        스크랩 생성/수정 전 이미지 URL의 무결성을 검증합니다.
        1. R2 커스텀 CDN URL이 아닌 경우 (Base64 Data URL, 외부 이미지 등) 허용 통과
        2. R2 CDN URL인 경우:
           - quote 경로 및 본인이 발급받은 키인지 검증 (타인 키 도용 차단)
           - R2 스토리지에 실제 업로드 완료된 객체인지 확인 (head_object)
           - 용량 상한 (5MB), Content-Type 및 16바이트 매직 넘버 검증
        """
        cls._verify_uploaded_image(
            member_id=member_id,
            image_url=image_url,
            category="quote",
            category_name="스크랩",
        )

    @classmethod
    def _detect_image_format_from_bytes(cls, data: bytes) -> str | None:
        """바이너리 헤더(매직 바이트) 기반 실제 이미지 포맷 탐지"""
        if len(data) < 4:
            return None
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if data.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return "gif"
        if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
            return "webp"
        return None

    @classmethod
    def _safe_delete_object(cls, key: str) -> None:
        """스토리지 객체 안전 삭제 (실패 시 로깅만 수행)"""
        try:
            s3 = cls.get_s3_client()
            s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
            logger.info("Cleaned up rejected or unused object: %s", key)
        except Exception as e:
            logger.warning("Failed to clean up object %s: %s", key, str(e))

    @classmethod
    def delete_image_if_exists(
        cls,
        image_url: str | None,
        member_id: uuid.UUID | None = None,
    ) -> None:
        """
        이전 커스텀 이미지(프로필 또는 스크랩)를 R2 스토리지에서 삭제합니다 (미사용 객체 누적 방지).
        삭제 실패 시에도 프로필/스크랩 수정 등 핵심 트랜잭션을 방해하지 않도록 예외는 기록만 합니다.
        """
        if not image_url or not image_url.strip():
            return

        clean_url = image_url.strip()
        cdn_prefix = settings.R2_PUBLIC_URL_PREFIX.rstrip("/")

        if not clean_url.startswith(cdn_prefix):
            return

        key = clean_url[len(cdn_prefix) :].lstrip("/")
        if not key:
            return

        # member_id가 지정되어 있다면 해당 사용자의 이미지인 경우에만 삭제
        if member_id is not None:
            filename = key.split("/")[-1]
            if not filename.startswith(f"{member_id}_"):
                return

        try:
            s3 = cls.get_s3_client()
            s3.delete_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
            )
            logger.info("Successfully cleaned up old image: key=%s", key)
        except Exception as e:
            logger.warning("Failed to clean up old image %s: %s", key, str(e))
