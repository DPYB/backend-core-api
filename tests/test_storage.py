import uuid
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    ImageNotFoundException,
    ImageStorageAccessDeniedException,
    InvalidImageUploadException,
)
from app.core.security import create_access_token, create_guest_token
from app.models.member import Member
from app.services.storage_service import (
    MAX_IMAGE_SIZE_BYTES,
    PRESIGNED_URL_EXPIRES_SECONDS,
    StorageService,
)


@pytest.fixture(autouse=True)
def mock_r2_settings(monkeypatch):
    """테스트 환경에서 R2 자격 증명 주입"""
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "mock-account-id")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "mock-access-key")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "mock-secret-key")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "dpyb-public")
    monkeypatch.setattr(settings, "R2_PUBLIC_URL_PREFIX", "https://cdn.ai0208.xyz")
    monkeypatch.setattr(settings, "R2_ENV_PREFIX", "beta")
    StorageService._s3_client = None
    yield
    StorageService._s3_client = None


@pytest.fixture
def mock_s3_client():
    """모킹된 S3 클라이언트 픽스처 (기본 get_object 매직 바이트 포함)"""
    mock = MagicMock()
    # 기본 get_object 반환값 (WebP 매직넘버 바이너리)
    body_mock = MagicMock()
    body_mock.read.return_value = b"RIFF\x24\x00\x00\x00WEBPVP8 "
    mock.get_object.return_value = {"Body": body_mock}

    StorageService._s3_client = mock
    yield mock
    StorageService._s3_client = None


@pytest.fixture
async def registered_member(db_session: AsyncSession) -> Member:
    """테스트용 일반 회원 생성"""
    member = Member(
        member_id=uuid.uuid4(),
        email=f"tester-{uuid.uuid4().hex[:6]}@example.com",
        nickname="프로필테스터",
        status="ACTIVE",
        profile_image_url="/profile/clia.png",
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member


@pytest.fixture
def member_auth_headers(registered_member: Member) -> dict[str, str]:
    """일반 회원 Bearer 토큰 헤더"""
    token = create_access_token(
        member_id=registered_member.member_id,
        email=registered_member.email,
        nickname=registered_member.nickname,
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. StorageService 단위 테스트
# ==============================================================================


def test_validate_content_type_and_extension_mapping():
    """MIME 타입에 따른 올바른 확장자 매핑 검증"""
    assert StorageService._validate_content_type("image/webp") == "webp"
    assert StorageService._validate_content_type("IMAGE/WEBP") == "webp"
    assert StorageService._validate_content_type("image/jpeg") == "jpg"
    assert StorageService._validate_content_type("image/png") == "png"
    assert StorageService._validate_content_type("image/gif") == "gif"

    # 비허용 타입 차단
    with pytest.raises(InvalidImageUploadException) as exc1:
        StorageService._validate_content_type("application/pdf")
    assert "지원하지 않는 이미지 형식" in str(exc1.value)

    with pytest.raises(InvalidImageUploadException) as exc2:
        StorageService._validate_content_type("text/html")
    assert "지원하지 않는 이미지 형식" in str(exc2.value)


def test_generate_storage_key_format():
    """스토리지 키 생성 규칙 검증 (category/env/{member_id}_{timestamp}_{uuid}.{ext})"""
    test_member_id = uuid.uuid4()
    key = StorageService.generate_storage_key("profile", test_member_id, "webp")

    parts = key.split("/")
    assert len(parts) == 3
    assert parts[0] == "profile"
    assert parts[1] == "beta"

    filename = parts[2]
    assert filename.startswith(f"{test_member_id}_")
    assert filename.endswith(".webp")


def test_missing_r2_credentials_raises_exception(monkeypatch):
    """R2 환경변수 누락 시 적절한 예외 발생 검증"""
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", None)
    StorageService._s3_client = None

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.get_s3_client()
    assert "스토리지 자격 증명이 설정되지 않았습니다" in str(exc.value)


def test_generate_profile_image_presigned_url(mock_s3_client: MagicMock):
    """Presigned PUT URL 발급 로직 및 만료시간(600초) 검증"""
    mock_s3_client.generate_presigned_url.return_value = (
        "https://r2.example.com/put?X-Amz-Signature=secret123"
    )

    test_member_id = uuid.uuid4()
    res = StorageService.generate_profile_image_presigned_url(
        member_id=test_member_id,
        content_type="image/png",
    )

    assert "presigned_url" in res
    assert "image_url" in res
    assert res["expires_in"] == PRESIGNED_URL_EXPIRES_SECONDS
    assert res["image_url"].endswith(".png")
    assert str(test_member_id) in res["image_url"]

    # boto3 generate_presigned_url 호출 파라미터 검증
    mock_s3_client.generate_presigned_url.assert_called_once()
    call_args = mock_s3_client.generate_presigned_url.call_args
    assert call_args.kwargs["ClientMethod"] == "put_object"
    assert call_args.kwargs["ExpiresIn"] == 600
    params = call_args.kwargs["Params"]
    assert params["Bucket"] == "dpyb-public"
    assert params["ContentType"] == "image/png"
    assert str(test_member_id) in params["Key"]


def test_verify_uploaded_profile_image_non_r2_pass(mock_s3_client: MagicMock):
    """프론트엔드 정적 이미지나 외부 소셜 URL은 R2 조회 없이 즉시 통과"""
    test_member_id = uuid.uuid4()

    # 상대 경로 정적 이미지
    StorageService.verify_uploaded_profile_image(test_member_id, "/profile/clia.png")
    # 외부 소셜 이미지
    StorageService.verify_uploaded_profile_image(
        test_member_id, "https://lh3.googleusercontent.com/avatar.jpg"
    )
    # 빈 문자열 또는 None
    StorageService.verify_uploaded_profile_image(test_member_id, "")
    StorageService.verify_uploaded_profile_image(test_member_id, None)

    mock_s3_client.head_object.assert_not_called()


def test_verify_uploaded_profile_image_other_member_key_denied(
    mock_s3_client: MagicMock,
):
    """타인의 member_id가 포함된 키 등록 시도 시 403 차단"""
    my_member_id = uuid.uuid4()
    other_member_id = uuid.uuid4()

    fake_url = f"https://cdn.ai0208.xyz/profile/beta/{other_member_id}_1729238400_abc12345.webp"

    with pytest.raises(ImageStorageAccessDeniedException) as exc:
        StorageService.verify_uploaded_profile_image(my_member_id, fake_url)
    assert "본인이 업로드한 프로필 이미지만" in str(exc.value)
    mock_s3_client.head_object.assert_not_called()


def test_verify_uploaded_profile_image_not_found(mock_s3_client: MagicMock):
    """R2에 실제로 업로드되지 않은 객체 등록 시도 시 404 차단"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/profile/beta/{my_member_id}_1729238400_abc12345.webp"
    )

    # 404 ClientError 발생 모킹
    error_response = {
        "Error": {"Code": "404", "Message": "Not Found"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with pytest.raises(ImageNotFoundException) as exc:
        StorageService.verify_uploaded_profile_image(my_member_id, target_url)
    assert "스토리지에 업로드되지 않은 이미지" in str(exc.value)


def test_detect_image_format_from_bytes():
    """바이너리 헤더 매직 넘버 기반 이미지 판별 검증"""
    assert StorageService._detect_image_format_from_bytes(b"\x89PNG\r\n\x1a\n") == "png"
    assert StorageService._detect_image_format_from_bytes(b"\xff\xd8\xff\xe0") == "jpg"
    assert StorageService._detect_image_format_from_bytes(b"GIF89a\x01\x00") == "gif"
    assert StorageService._detect_image_format_from_bytes(b"GIF87a\x01\x00") == "gif"
    assert (
        StorageService._detect_image_format_from_bytes(b"RIFF\x24\x00\x00\x00WEBPVP8 ")
        == "webp"
    )
    # 위조 파일 (HTML, 텍스트, 빈 바이트 등)
    assert (
        StorageService._detect_image_format_from_bytes(
            b"<html><body>test</body></html>"
        )
        is None
    )
    assert StorageService._detect_image_format_from_bytes(b"") is None
    assert StorageService._detect_image_format_from_bytes(b"123") is None


def test_verify_uploaded_profile_image_size_exceeded_and_cleanup(
    mock_s3_client: MagicMock,
):
    """5MB 초과 이미지 등록 시도 시 400 차단 및 R2 불량 객체 자동 삭제 검증"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/profile/beta/{my_member_id}_1729238400_abc12345.webp"
    )

    mock_s3_client.head_object.return_value = {
        "ContentLength": MAX_IMAGE_SIZE_BYTES + 1024,
        "ContentType": "image/webp",
    }

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_profile_image(my_member_id, target_url)
    assert "최대 허용치(5MB)를 초과" in str(exc.value)

    # 불량 객체가 R2에서 즉시 삭제되었는지 확인
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"profile/beta/{my_member_id}_1729238400_abc12345.webp",
    )


def test_verify_uploaded_profile_image_fake_bytes_reject_and_cleanup(
    mock_s3_client: MagicMock,
):
    """실제 파일이 이미지가 아닌 위조 텍스트/스크립트일 때 400 차단 및 R2 자동 삭제 검증"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/profile/beta/{my_member_id}_1729238400_fake.webp"
    )

    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 10,
        "ContentType": "image/webp",
    }
    # get_object에서 위조 HTML 바이너리 반환 모킹
    fake_body = MagicMock()
    fake_body.read.return_value = b"<script>alert(1)</script>"
    mock_s3_client.get_object.return_value = {"Body": fake_body}

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_profile_image(my_member_id, target_url)
    assert "유효한 이미지" in str(exc.value)

    # R2에서 즉시 불량 객체 삭제되었는지 확인
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"profile/beta/{my_member_id}_1729238400_fake.webp",
    )


def test_verify_uploaded_profile_image_invalid_r2_path_denied(
    mock_s3_client: MagicMock,
):
    """profile/ 경로가 아닌 잘못된 R2 객체 키 등록 시도 시 400 차단"""
    my_member_id = uuid.uuid4()
    bad_path_url = f"https://cdn.ai0208.xyz/admin/secret/{my_member_id}_file.webp"

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_profile_image(my_member_id, bad_path_url)
    assert "저장 경로가 올바르지 않습니다" in str(exc.value)


def test_verify_uploaded_profile_image_success(mock_s3_client: MagicMock):
    """정상 객체 검증 통과 (헤더 및 매직 바이트 검증 성공)"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/profile/beta/{my_member_id}_1729238400_abc12345.webp"
    )

    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 500,  # 500KB
        "ContentType": "image/webp",
    }

    StorageService.verify_uploaded_profile_image(my_member_id, target_url)
    mock_s3_client.head_object.assert_called_once()
    mock_s3_client.get_object.assert_called_once()


def test_delete_image_if_exists(mock_s3_client: MagicMock):
    """이전 프로필 이미지 정리 호출 검증"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/profile/beta/{my_member_id}_1729238400_old123.webp"
    )

    StorageService.delete_image_if_exists(target_url, member_id=my_member_id)
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"profile/beta/{my_member_id}_1729238400_old123.webp",
    )


# ==============================================================================
# 2. 엔드포인트 통합 테스트 (Presigned URL & PATCH)
# ==============================================================================


@pytest.mark.asyncio
async def test_presigned_url_unauthorized(client: AsyncClient):
    """비인증 요청 시 401 차단"""
    resp = await client.post(
        "/api/v1/users/me/profile-image/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": ""},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_presigned_url_guest_blocked(client: AsyncClient):
    """게스트 계정의 Presigned URL 발급 시도 시 403 차단"""
    guest_token = create_guest_token(guest_id=str(uuid.uuid4()))
    resp = await client.post(
        "/api/v1/users/me/profile-image/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_presigned_url_demo_blocked(client: AsyncClient):
    """데모 계정의 Presigned URL 발급 시도 시 403 차단"""
    demo_token = create_access_token(
        member_id=uuid.UUID(settings.DEMO_MEMBER_ID),
        email="demo@dontpawget.com",
        nickname="데모냥이",
    )
    resp = await client.post(
        "/api/v1/users/me/profile-image/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": f"Bearer {demo_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_presigned_url_invalid_content_type(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
):
    """지원하지 않는 Content-Type 요청 시 400 차단"""
    resp = await client.post(
        "/api/v1/users/me/profile-image/presigned-url",
        json={"contentType": "application/pdf"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_IMAGE_UPLOAD"


@pytest.mark.asyncio
async def test_presigned_url_success(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """정상 회원의 Presigned URL 발급 성공 (200 OK)"""
    mock_s3_client.generate_presigned_url.return_value = (
        "https://r2.cloudflarestorage.com/dpyb-public/profile/beta/file.webp?sig=123"
    )

    resp = await client.post(
        "/api/v1/users/me/profile-image/presigned-url",
        json={"contentType": "image/webp"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "presignedUrl" in data
    assert "imageUrl" in data
    assert data["expiresIn"] == 600
    assert str(registered_member.member_id) in data["imageUrl"]
    assert data["imageUrl"].endswith(".webp")


@pytest.mark.asyncio
async def test_alias_presigned_url_success(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """별칭 엔드포인트(/api/v1/members/me/...) 정상 발급 성공 (200 OK)"""
    mock_s3_client.generate_presigned_url.return_value = (
        "https://r2.cloudflarestorage.com/dpyb-public/profile/beta/file.png?sig=123"
    )

    resp = await client.post(
        "/api/v1/members/me/profile-image/presigned-url",
        json={"contentType": "image/png"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imageUrl"].endswith(".png")


@pytest.mark.asyncio
async def test_update_profile_with_other_member_image_denied(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
):
    """타인의 객체 키로 프로필 갱신 시도 시 403 차단"""
    other_uuid = uuid.uuid4()
    stolen_url = (
        f"https://cdn.ai0208.xyz/profile/beta/{other_uuid}_1729238400_abc12345.webp"
    )

    resp = await client.patch(
        "/api/v1/users/me",
        json={"profileImageUrl": stolen_url},
        headers=member_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "IMAGE_STORAGE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_update_profile_with_nonexistent_image_denied(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """R2에 실제 업로드되지 않은 객체로 프로필 갱신 시도 시 404 차단"""
    fake_url = f"https://cdn.ai0208.xyz/profile/beta/{registered_member.member_id}_1729238400_abc12345.webp"

    error_response = {
        "Error": {"Code": "404", "Message": "Not Found"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    resp = await client.patch(
        "/api/v1/users/me",
        json={"profileImageUrl": fake_url},
        headers=member_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "IMAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_profile_e2e_success_and_cleanup(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
    db_session: AsyncSession,
):
    """
    E2E 검증:
    1. 이전 커스텀 프로필 설정 상태에서 신규 R2 이미지로 프로필 갱신
    2. head_object로 무결성 검증 통과
    3. delete_object로 이전 커스텀 이미지 정리 확인
    4. DB에 신규 profile_image_url 정상 저장 확인
    """
    old_custom_url = f"https://cdn.ai0208.xyz/profile/beta/{registered_member.member_id}_1700000000_old.webp"
    registered_member.profile_image_url = old_custom_url
    await db_session.commit()

    new_custom_url = f"https://cdn.ai0208.xyz/profile/beta/{registered_member.member_id}_1729238400_new.webp"

    # head_object 성공 모킹
    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 200,
        "ContentType": "image/webp",
    }

    resp = await client.patch(
        "/api/v1/users/me",
        json={
            "nickname": "새닉네임",
            "profileImageUrl": new_custom_url,
        },
        headers=member_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nickname"] == "새닉네임"
    assert body["profileImageUrl"] == new_custom_url

    # 이전 이미지 delete_object 호출 확인
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"profile/beta/{registered_member.member_id}_1700000000_old.webp",
    )


@pytest.mark.asyncio
async def test_update_profile_other_fields_preserved(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
):
    """닉네임이나 생년월일만 갱신할 때 R2 검증 없이 기존 기능 정상 작동 확인"""
    resp = await client.patch(
        "/api/v1/users/me",
        json={"nickname": "오직닉네임만변경"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "오직닉네임만변경"


# ==============================================================================
# 3. Scrap Presigned URL 및 이미지 무결성 검증/정리 테스트 (Phase 59)
# ==============================================================================


def test_generate_scrap_image_presigned_url(mock_s3_client: MagicMock):
    """스크랩 Presigned PUT URL 발급 로직, 키 경로(quote/beta/...) 및 만료시간 검증"""
    mock_s3_client.generate_presigned_url.return_value = (
        "https://r2.example.com/quote-put?X-Amz-Signature=secret456"
    )

    test_member_id = uuid.uuid4()
    res = StorageService.generate_scrap_image_presigned_url(
        member_id=test_member_id,
        content_type="image/webp",
    )

    assert "presigned_url" in res
    assert "image_url" in res
    assert res["expires_in"] == PRESIGNED_URL_EXPIRES_SECONDS
    assert res["image_url"].endswith(".webp")
    assert f"/quote/beta/{test_member_id}_" in res["image_url"]

    # boto3 호출 파라미터 검증
    mock_s3_client.generate_presigned_url.assert_called_once()
    call_args = mock_s3_client.generate_presigned_url.call_args
    assert call_args.kwargs["ClientMethod"] == "put_object"
    assert call_args.kwargs["ExpiresIn"] == 600
    params = call_args.kwargs["Params"]
    assert params["Bucket"] == "dpyb-public"
    assert params["ContentType"] == "image/webp"
    assert params["Key"].startswith(f"quote/beta/{test_member_id}_")


def test_verify_uploaded_scrap_image_non_r2_and_base64_pass(
    mock_s3_client: MagicMock,
):
    """Base64 Data URL, 외부 URL 및 빈 문자열은 R2 조회 없이 통과 (하위 호환성)"""
    test_member_id = uuid.uuid4()

    # Base64 Data URL
    StorageService.verify_uploaded_scrap_image(
        test_member_id,
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    )
    # 외부 이미지 URL
    StorageService.verify_uploaded_scrap_image(
        test_member_id, "https://example.com/scraps/quote.jpg"
    )
    # 빈 문자열 또는 None
    StorageService.verify_uploaded_scrap_image(test_member_id, "")
    StorageService.verify_uploaded_scrap_image(test_member_id, None)

    mock_s3_client.head_object.assert_not_called()


def test_verify_uploaded_scrap_image_other_member_key_denied(
    mock_s3_client: MagicMock,
):
    """타인의 member_id가 포함된 스크랩 키 등록 시도 시 403 차단"""
    my_member_id = uuid.uuid4()
    other_member_id = uuid.uuid4()

    fake_url = (
        f"https://cdn.ai0208.xyz/quote/beta/{other_member_id}_1729238400_abc12345.webp"
    )

    with pytest.raises(ImageStorageAccessDeniedException) as exc:
        StorageService.verify_uploaded_scrap_image(my_member_id, fake_url)
    assert "본인이 업로드한 스크랩 이미지만" in str(exc.value)
    mock_s3_client.head_object.assert_not_called()


def test_verify_uploaded_scrap_image_not_found(mock_s3_client: MagicMock):
    """R2에 실제로 업로드되지 않은 스크랩 객체 등록 시도 시 404 차단"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/quote/beta/{my_member_id}_1729238400_abc12345.webp"
    )

    error_response = {
        "Error": {"Code": "404", "Message": "Not Found"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with pytest.raises(ImageNotFoundException) as exc:
        StorageService.verify_uploaded_scrap_image(my_member_id, target_url)
    assert "스토리지에 업로드되지 않은 이미지" in str(exc.value)


def test_verify_uploaded_scrap_image_size_exceeded_and_cleanup(
    mock_s3_client: MagicMock,
):
    """5MB 초과 스크랩 이미지 등록 시도 시 400 차단 및 R2 불량 객체 자동 삭제 검증"""
    my_member_id = uuid.uuid4()
    target_url = f"https://cdn.ai0208.xyz/quote/beta/{my_member_id}_1729238400_big.webp"

    mock_s3_client.head_object.return_value = {
        "ContentLength": MAX_IMAGE_SIZE_BYTES + 2048,
        "ContentType": "image/webp",
    }

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_scrap_image(my_member_id, target_url)
    assert "최대 허용치(5MB)를 초과" in str(exc.value)

    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"quote/beta/{my_member_id}_1729238400_big.webp",
    )


def test_verify_uploaded_scrap_image_fake_bytes_reject_and_cleanup(
    mock_s3_client: MagicMock,
):
    """실제 파일이 이미지가 아닌 위조 텍스트일 때 400 차단 및 R2 자동 삭제 검증"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/quote/beta/{my_member_id}_1729238400_fake.webp"
    )

    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 5,
        "ContentType": "image/webp",
    }
    fake_body = MagicMock()
    fake_body.read.return_value = b"Hello, I am a plain text file."
    mock_s3_client.get_object.return_value = {"Body": fake_body}

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_scrap_image(my_member_id, target_url)
    assert "유효한 이미지" in str(exc.value)

    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"quote/beta/{my_member_id}_1729238400_fake.webp",
    )


def test_verify_uploaded_scrap_image_invalid_r2_path_denied(
    mock_s3_client: MagicMock,
):
    """quote/ 경로가 아닌 잘못된 R2 객체 키(예: profile/...) 등록 시도 시 400 차단"""
    my_member_id = uuid.uuid4()
    bad_path_url = f"https://cdn.ai0208.xyz/profile/beta/{my_member_id}_file.webp"

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_scrap_image(my_member_id, bad_path_url)
    assert "스크랩 이미지 저장 경로가 올바르지 않습니다" in str(exc.value)


def test_verify_uploaded_scrap_image_success(mock_s3_client: MagicMock):
    """정상 스크랩 객체 검증 통과 (헤더 및 매직 바이트 검증 성공)"""
    my_member_id = uuid.uuid4()
    target_url = (
        f"https://cdn.ai0208.xyz/quote/beta/{my_member_id}_1729238400_valid.webp"
    )

    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 300,  # 300KB
        "ContentType": "image/webp",
    }

    StorageService.verify_uploaded_scrap_image(my_member_id, target_url)
    mock_s3_client.head_object.assert_called_once()
    mock_s3_client.get_object.assert_called_once()


@pytest.mark.asyncio
async def test_scrap_presigned_url_unauthorized(client: AsyncClient):
    """비인증 요청 시 401 차단"""
    resp = await client.post(
        "/api/v1/library/scraps/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": ""},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_scrap_presigned_url_guest_blocked(client: AsyncClient):
    """게스트 계정의 스크랩 Presigned URL 발급 시도 시 403 차단"""
    guest_token = create_guest_token(guest_id=str(uuid.uuid4()))
    resp = await client.post(
        "/api/v1/library/scraps/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scrap_presigned_url_demo_blocked(client: AsyncClient):
    """데모 계정의 스크랩 Presigned URL 발급 시도 시 403 차단"""
    demo_token = create_access_token(
        member_id=uuid.UUID(settings.DEMO_MEMBER_ID),
        email="demo@dontpawget.com",
        nickname="데모냥이",
    )
    resp = await client.post(
        "/api/v1/library/scraps/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": f"Bearer {demo_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scrap_presigned_url_invalid_content_type(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
):
    """지원하지 않는 Content-Type 요청 시 400 차단"""
    resp = await client.post(
        "/api/v1/library/scraps/presigned-url",
        json={"contentType": "application/zip"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_IMAGE_UPLOAD"


@pytest.mark.asyncio
async def test_scrap_presigned_url_success(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """정상 회원의 스크랩 Presigned URL 발급 성공 (200 OK)"""
    mock_s3_client.generate_presigned_url.return_value = (
        "https://r2.cloudflarestorage.com/dpyb-public/quote/beta/file.webp?sig=456"
    )

    resp = await client.post(
        "/api/v1/library/scraps/presigned-url",
        json={"contentType": "image/webp"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "presignedUrl" in data
    assert "imageUrl" in data
    assert data["expiresIn"] == 600
    assert f"/quote/beta/{registered_member.member_id}_" in data["imageUrl"]
    assert data["imageUrl"].endswith(".webp")


@pytest.mark.asyncio
async def test_create_scrap_with_other_member_image_denied(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
):
    """타인의 객체 키로 스크랩 등록 시도 시 403 차단"""
    # 1. 도서 생성
    book_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "스크랩 보안 테스트 도서", "author": "저자"},
        headers=member_auth_headers,
    )
    assert book_resp.status_code == 201
    book_id = book_resp.json()["bookId"]

    # 2. 타인의 키로 스크랩 생성 시도
    other_uuid = uuid.uuid4()
    stolen_url = (
        f"https://cdn.ai0208.xyz/quote/beta/{other_uuid}_1729238400_abc12345.webp"
    )

    resp = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "도용 시도 문장입니다.",
            "scrapImageUrl": stolen_url,
        },
        headers=member_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "IMAGE_STORAGE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_create_scrap_with_nonexistent_image_denied(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """R2에 실제 업로드되지 않은 객체로 스크랩 생성 시도 시 404 차단"""
    # 1. 도서 생성
    book_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "스크랩 미존재 테스트 도서", "author": "저자"},
        headers=member_auth_headers,
    )
    book_id = book_resp.json()["bookId"]

    fake_url = f"https://cdn.ai0208.xyz/quote/beta/{registered_member.member_id}_1729238400_ghost.webp"

    error_response = {
        "Error": {"Code": "404", "Message": "Not Found"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    resp = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "유령 이미지 문장입니다.",
            "scrapImageUrl": fake_url,
        },
        headers=member_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "IMAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_scrap_r2_lifecycle_and_cleanup_e2e(
    client: AsyncClient,
    registered_member: Member,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """
    스크랩 E2E 라이프사이클 및 이미지 정리 검증:
    1. R2 이미지로 스크랩 등록 (head_object 무결성 검증 통과)
    2. 신규 R2 이미지로 스크랩 수정 -> 이전 R2 이미지 delete_object 호출 확인
    3. 스크랩 삭제 -> 해당 R2 이미지 delete_object 호출 확인
    """
    # 1. 도서 생성
    book_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "스크랩 E2E 도서", "author": "저자"},
        headers=member_auth_headers,
    )
    book_id = book_resp.json()["bookId"]

    # 2. 첫 번째 R2 이미지로 스크랩 생성
    img1_url = f"https://cdn.ai0208.xyz/quote/beta/{registered_member.member_id}_1729238400_img1.webp"
    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 150,
        "ContentType": "image/webp",
    }

    create_resp = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "인간은 생각하는 갈대이다.",
            "pageNumber": 42,
            "scrapImageUrl": img1_url,
            "memo": "파스칼",
        },
        headers=member_auth_headers,
    )
    assert create_resp.status_code == 201
    scrap_id = create_resp.json()["scrapId"]
    assert create_resp.json()["scrapImageUrl"] == img1_url

    # 3. 두 번째 R2 이미지로 스크랩 수정
    img2_url = f"https://cdn.ai0208.xyz/quote/beta/{registered_member.member_id}_1729239999_img2.webp"
    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 180,
        "ContentType": "image/webp",
    }

    update_resp = await client.patch(
        f"/api/v1/library/scraps/{scrap_id}",
        json={
            "sentence": "인간은 생각하는 갈대이다. (수정됨)",
            "scrapImageUrl": img2_url,
        },
        headers=member_auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["scrapImageUrl"] == img2_url

    # 이전 이미지 img1_url에 대해 delete_object가 호출되었는지 확인
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"quote/beta/{registered_member.member_id}_1729238400_img1.webp",
    )
    mock_s3_client.delete_object.reset_mock()

    # 4. 스크랩 삭제 -> img2_url에 대해 delete_object 호출 확인
    del_resp = await client.delete(
        f"/api/v1/library/scraps/{scrap_id}",
        headers=member_auth_headers,
    )
    assert del_resp.status_code == 204

    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key=f"quote/beta/{registered_member.member_id}_1729239999_img2.webp",
    )


# ==============================================================================
# 4. Book Cover Presigned URL 및 이미지 무결성 검증/정리 테스트 (Phase 60)
# ==============================================================================


def test_generate_book_cover_presigned_url(mock_s3_client: MagicMock):
    """도서 표지 Presigned PUT URL 발급 로직, 키 경로(frontcover/beta/...) 및 반환 명세 검증"""
    mock_s3_client.generate_presigned_url.return_value = (
        "https://r2.example.com/cover-put?X-Amz-Signature=secret789"
    )

    test_member_id = uuid.uuid4()
    res = StorageService.generate_book_cover_presigned_url(
        member_id=test_member_id,
        content_type="image/webp",
    )

    # 전달주신 스펙 키 검증
    assert "upload_url" in res
    assert "public_url" in res
    assert "key" in res
    assert "presigned_url" in res
    assert "image_url" in res
    assert res["expires_in"] == PRESIGNED_URL_EXPIRES_SECONDS

    assert res["key"].startswith("frontcover/beta/")
    assert res["key"].endswith(".webp")
    assert res["public_url"].endswith(res["key"])

    # boto3 호출 파라미터 검증
    mock_s3_client.generate_presigned_url.assert_called_once()
    call_args = mock_s3_client.generate_presigned_url.call_args
    assert call_args.kwargs["ClientMethod"] == "put_object"
    assert call_args.kwargs["ExpiresIn"] == 600
    params = call_args.kwargs["Params"]
    assert params["Bucket"] == "dpyb-public"
    assert params["ContentType"] == "image/webp"
    assert params["Key"] == res["key"]


def test_verify_uploaded_book_cover_non_r2_pass(mock_s3_client: MagicMock):
    """외부 서점 표지 URL 및 빈 문자열은 R2 조회 없이 통과 (하위 호환성)"""
    # 외부 서점 CDN URL
    StorageService.verify_uploaded_book_cover(
        "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791191587524.jpg"
    )
    # 국립도서관/알라딘 등 외부 URL
    StorageService.verify_uploaded_book_cover("https://cover.nl.go.kr/cover.jpg")
    # 빈 문자열 또는 None
    StorageService.verify_uploaded_book_cover("")
    StorageService.verify_uploaded_book_cover(None)

    mock_s3_client.head_object.assert_not_called()


def test_verify_uploaded_book_cover_invalid_path_denied(mock_s3_client: MagicMock):
    """frontcover/ 경로가 아닌 잘못된 R2 객체 키(예: profile/...) 등록 시도 시 400 차단"""
    bad_url = "https://cdn.ai0208.xyz/profile/beta/file.webp"

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_book_cover(bad_url)
    assert "도서 표지 이미지 저장 경로가 올바르지 않습니다" in str(exc.value)


def test_verify_uploaded_book_cover_not_found(mock_s3_client: MagicMock):
    """R2에 실제로 업로드되지 않은 표지 객체 등록 시도 시 404 차단"""
    target_url = "https://cdn.ai0208.xyz/frontcover/beta/nonexistent.webp"

    error_response = {
        "Error": {"Code": "404", "Message": "Not Found"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with pytest.raises(ImageNotFoundException) as exc:
        StorageService.verify_uploaded_book_cover(target_url)
    assert "스토리지에 업로드되지 않은 이미지" in str(exc.value)


def test_verify_uploaded_book_cover_size_exceeded_and_cleanup(
    mock_s3_client: MagicMock,
):
    """5MB 초과 도서 표지 등록 시도 시 400 차단 및 R2 불량 객체 자동 삭제 검증"""
    target_url = "https://cdn.ai0208.xyz/frontcover/beta/huge_cover.webp"

    mock_s3_client.head_object.return_value = {
        "ContentLength": MAX_IMAGE_SIZE_BYTES + 4096,
        "ContentType": "image/webp",
    }

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_book_cover(target_url)
    assert "최대 허용치(5MB)를 초과" in str(exc.value)

    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key="frontcover/beta/huge_cover.webp",
    )


def test_verify_uploaded_book_cover_fake_bytes_reject_and_cleanup(
    mock_s3_client: MagicMock,
):
    """실제 파일이 이미지가 아닌 위조 텍스트일 때 400 차단 및 R2 자동 삭제 검증"""
    target_url = "https://cdn.ai0208.xyz/frontcover/beta/fake_cover.webp"

    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 10,
        "ContentType": "image/webp",
    }
    fake_body = MagicMock()
    fake_body.read.return_value = b"<!DOCTYPE html><html>fake</html>"
    mock_s3_client.get_object.return_value = {"Body": fake_body}

    with pytest.raises(InvalidImageUploadException) as exc:
        StorageService.verify_uploaded_book_cover(target_url)
    assert "유효한 이미지" in str(exc.value)

    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key="frontcover/beta/fake_cover.webp",
    )


def test_verify_uploaded_book_cover_success(mock_s3_client: MagicMock):
    """정상 도서 표지 객체 검증 통과 (헤더 및 매직 바이트 검증 성공)"""
    target_url = "https://cdn.ai0208.xyz/frontcover/beta/valid_cover.webp"

    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 400,  # 400KB
        "ContentType": "image/webp",
    }

    StorageService.verify_uploaded_book_cover(target_url)
    mock_s3_client.head_object.assert_called_once()
    mock_s3_client.get_object.assert_called_once()


@pytest.mark.asyncio
async def test_book_cover_presigned_url_unauthorized(client: AsyncClient):
    """비인증 요청 시 401 차단"""
    resp = await client.post(
        "/api/v1/library/books/cover/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": ""},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_book_cover_presigned_url_guest_blocked(client: AsyncClient):
    """게스트 계정의 도서 표지 Presigned URL 발급 시도 시 403 차단"""
    guest_token = create_guest_token(guest_id=str(uuid.uuid4()))
    resp = await client.post(
        "/api/v1/library/books/cover/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_book_cover_presigned_url_demo_blocked(client: AsyncClient):
    """데모 계정의 도서 표지 Presigned URL 발급 시도 시 403 차단"""
    demo_token = create_access_token(
        member_id=uuid.UUID(settings.DEMO_MEMBER_ID),
        email="demo@dontpawget.com",
        nickname="데모냥이",
    )
    resp = await client.post(
        "/api/v1/library/books/cover/presigned-url",
        json={"contentType": "image/webp"},
        headers={"Authorization": f"Bearer {demo_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_book_cover_presigned_url_invalid_content_type(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
):
    """지원하지 않는 Content-Type 요청 시 400 차단"""
    resp = await client.post(
        "/api/v1/library/books/cover/presigned-url",
        json={"contentType": "application/x-executable"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_IMAGE_UPLOAD"


@pytest.mark.asyncio
async def test_book_cover_presigned_url_success(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """정상 회원의 도서 표지 Presigned URL 발급 성공 (200 OK 및 명세 JSON 구조 검증)"""
    mock_s3_client.generate_presigned_url.return_value = "https://r2.cloudflarestorage.com/dpyb-public/frontcover/beta/custom.webp?sig=789"

    resp = await client.post(
        "/api/v1/library/books/cover/presigned-url",
        json={"contentType": "image/webp"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()

    # 명세 구조: { status: "success", data: { uploadUrl, publicUrl, key } }
    assert body["status"] == "success"
    data = body["data"]
    assert "uploadUrl" in data
    assert "publicUrl" in data
    assert "key" in data
    assert data["key"].startswith("frontcover/beta/")
    assert data["key"].endswith(".webp")
    assert data["publicUrl"].endswith(data["key"])
    assert data["expiresIn"] == 600

    # 듀얼 호환 필드 검증
    assert data["uploadUrl"] == data["presignedUrl"]
    assert data["publicUrl"] == data["imageUrl"]


@pytest.mark.asyncio
async def test_create_book_with_nonexistent_cover_denied(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """R2에 실제 업로드되지 않은 커스텀 표지로 도서 등록 시도 시 404 차단"""
    fake_cover = "https://cdn.ai0208.xyz/frontcover/beta/ghost_cover.webp"

    error_response = {
        "Error": {"Code": "404", "Message": "Not Found"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "미존재 표지 도서",
            "author": "작가",
            "coverUrl": fake_cover,
        },
        headers=member_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "IMAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_book_cover_r2_lifecycle_and_cleanup_e2e(
    client: AsyncClient,
    member_auth_headers: dict[str, str],
    mock_s3_client: MagicMock,
):
    """
    도서 커스텀 표지 E2E 라이프사이클 및 이미지 정리 검증:
    1. 커스텀 R2 표지로 도서 생성 (head_object 무결성 검증 통과)
    2. 신규 커스텀 R2 표지로 도서 수정 -> 이전 R2 표지 delete_object 호출 확인
    3. 도서 삭제 -> 해당 커스텀 R2 표지 delete_object 호출 확인
    """
    # 1. 첫 번째 R2 표지로 도서 생성
    cover1_url = "https://cdn.ai0208.xyz/frontcover/beta/custom_cover1.webp"
    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 350,
        "ContentType": "image/webp",
    }

    create_resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "커스텀 표지 도서",
            "author": "멋진 작가",
            "coverUrl": cover1_url,
        },
        headers=member_auth_headers,
    )
    assert create_resp.status_code == 201
    book_id = create_resp.json()["bookId"]
    assert create_resp.json()["coverUrl"] == cover1_url

    # 2. 두 번째 R2 표지로 도서 수정
    cover2_url = "https://cdn.ai0208.xyz/frontcover/beta/custom_cover2.webp"
    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024 * 450,
        "ContentType": "image/webp",
    }

    update_resp = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "커스텀 표지 도서 (수정)",
            "author": "멋진 작가",
            "coverUrl": cover2_url,
            "readingStatus": "READING",
        },
        headers=member_auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["coverUrl"] == cover2_url

    # 이전 커스텀 표지 cover1_url에 대해 delete_object가 호출되었는지 확인
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key="frontcover/beta/custom_cover1.webp",
    )
    mock_s3_client.delete_object.reset_mock()

    # 3. 도서 삭제 -> cover2_url에 대해 delete_object 호출 확인
    del_resp = await client.delete(
        f"/api/v1/library/books/{book_id}",
        headers=member_auth_headers,
    )
    assert del_resp.status_code == 204

    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="dpyb-public",
        Key="frontcover/beta/custom_cover2.webp",
    )
