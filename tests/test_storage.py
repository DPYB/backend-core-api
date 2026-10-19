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
