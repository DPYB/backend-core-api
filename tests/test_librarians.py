import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_librarian_types_catalog(client: AsyncClient):
    resp = await client.get("/api/v1/librarian-types")
    assert resp.status_code == 200
    types = resp.json()["types"]
    assert len(types) == 4
    type_names = [t["type"] for t in types]
    assert "CAT" in type_names
    assert "SHOEBILL" in type_names
    assert "SEA_SLUG" in type_names
    assert "GECKO" in type_names


@pytest.mark.asyncio
async def test_acquire_librarian_and_duplicate_conflict(client: AsyncClient):
    # 1. 고양이 사서 획득
    req = {"type": "CAT", "name": "파란이"}
    resp1 = await client.post("/api/v1/librarians", json=req)
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["name"] == "파란이"
    assert data1["type"] == "CAT"
    assert data1["level"] == 1
    assert data1["experience"] == 0
    assert data1["isRepresentative"] is False

    # 2. 동일 타입 중복 획득 시도 -> 409
    resp2 = await client.post(
        "/api/v1/librarians", json={"type": "CAT", "name": "파란이2"}
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "LIBRARIAN_ALREADY_OWNED"


@pytest.mark.asyncio
async def test_representative_librarian_lifecycle(client: AsyncClient):
    # 1. 대표 사서가 없는 상태에서 조회 -> 404
    rep_resp = await client.get("/api/v1/librarians/representative")
    assert rep_resp.status_code == 404
    assert rep_resp.json()["code"] == "REPRESENTATIVE_LIBRARIAN_NOT_SELECTED"

    # 2. 사서 2마리 획득
    cat_id = (
        await client.post("/api/v1/librarians", json={"type": "CAT", "name": "냥이"})
    ).json()["librarianId"]
    bird_id = (
        await client.post(
            "/api/v1/librarians", json={"type": "SHOEBILL", "name": "슈빌이"}
        )
    ).json()["librarianId"]

    # 3. 고양이를 대표 사서로 지정
    set_rep_resp = await client.patch(f"/api/v1/librarians/{cat_id}/representative")
    assert set_rep_resp.status_code == 200
    assert set_rep_resp.json()["librarianId"] == cat_id
    assert set_rep_resp.json()["isRepresentative"] is True

    # 4. 대표 사서 조회
    curr_rep = await client.get("/api/v1/librarians/representative")
    assert curr_rep.status_code == 200
    assert curr_rep.json()["librarianId"] == cat_id

    # 5. 슈빌을 대표 사서로 변경
    set_bird_rep = await client.patch(f"/api/v1/librarians/{bird_id}/representative")
    assert set_bird_rep.status_code == 200

    # 6. 내 사서 목록 조회 -> 슈빌만 대표이고 고양이는 해제되었는지 확인
    my_libs = (await client.get("/api/v1/librarians")).json()
    cat_item = next(item for item in my_libs if item["librarianId"] == cat_id)
    bird_item = next(item for item in my_libs if item["librarianId"] == bird_id)
    assert cat_item["isRepresentative"] is False
    assert bird_item["isRepresentative"] is True


@pytest.mark.asyncio
async def test_rename_and_dismiss_librarian(client: AsyncClient):
    lib_id = (
        await client.post(
            "/api/v1/librarians", json={"type": "GECKO", "name": "초기이름"}
        )
    ).json()["librarianId"]

    # 개명
    rename_resp = await client.patch(
        f"/api/v1/librarians/{lib_id}", json={"name": "새이름"}
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["name"] == "새이름"

    # 방출 (삭제)
    del_resp = await client.delete(f"/api/v1/librarians/{lib_id}")
    assert del_resp.status_code == 204

    # 내 사서 목록에서 제외되었는지 확인
    my_libs = (await client.get("/api/v1/librarians")).json()
    assert not any(item["librarianId"] == lib_id for item in my_libs)


@pytest.mark.asyncio
async def test_librarian_types_catalog_metadata(client: AsyncClient):
    resp = await client.get("/api/v1/librarian-types")
    assert resp.status_code == 200
    types = {t["type"]: t for t in resp.json()["types"]}

    # CAT (블루)
    cat = types["CAT"]
    assert cat["defaultName"] == "블루"
    assert cat["species"] == "러시안 블루"
    assert cat["mbti"] == "INTJ"
    assert "철학" in cat["genres"]
    assert cat["endingStyle"] == "~냥"

    # SHOEBILL (슈빌)
    shoebill = types["SHOEBILL"]
    assert shoebill["defaultName"] == "슈빌"
    assert shoebill["species"] == "넙적부리황새"
    assert shoebill["mbti"] == "ISTP"
    assert "자연과학" in shoebill["genres"]
    assert shoebill["endingStyle"] == "~두둥"

    # SEA_SLUG (누디) - 기존 바다달팽이 -> 누디 변경 확인
    sea_slug = types["SEA_SLUG"]
    assert sea_slug["defaultName"] == "누디"
    assert sea_slug["species"] == "갯민숭달팽이"
    assert sea_slug["mbti"] == "INFP"
    assert "문학" in sea_slug["genres"]
    assert sea_slug["endingStyle"] == "~누누"

    # GECKO (게코)
    gecko = types["GECKO"]
    assert gecko["defaultName"] == "게코"
    assert gecko["species"] == "게코 도마뱀"
    assert gecko["mbti"] == "ENFJ"
    assert "역사" in gecko["genres"]
    assert gecko["endingStyle"] == "~크크"


@pytest.mark.asyncio
async def test_acquire_librarian_default_name_fallback(client: AsyncClient):
    # SEA_SLUG 획득 시 이름 생략 -> 기본 표시명 "누디" 자동 지정
    resp = await client.post("/api/v1/librarians", json={"type": "SEA_SLUG"})
    assert resp.status_code == 201
    slug_data = resp.json()
    assert slug_data["name"] == "누디"
    assert slug_data["type"] == "SEA_SLUG"

    # 대표 사서 지정
    slug_id = slug_data["librarianId"]
    set_rep = await client.patch(f"/api/v1/librarians/{slug_id}/representative")
    assert set_rep.status_code == 200
    rep_data = set_rep.json()
    assert rep_data["name"] == "누디"
    assert rep_data["defaultName"] == "누디"
    assert rep_data["species"] == "갯민숭달팽이"
    assert rep_data["mbti"] == "INFP"
    assert "문학" in rep_data["genres"]
    assert rep_data["endingStyle"] == "~누누"


@pytest.mark.asyncio
async def test_member_profile_librarian_info_and_alias(client: AsyncClient):
    # 1. 개발자 간편 로그인으로 신규 회원 생성 (기본 CAT "블루" 대표 사서 자동 부여)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "nuditest@example.com"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. GET /api/v1/users/me 조회 시 대표 사서 정보 확인
    users_me_resp = await client.get("/api/v1/users/me", headers=headers)
    assert users_me_resp.status_code == 200
    profile1 = users_me_resp.json()
    assert profile1["librarianType"] == "CAT"
    assert profile1["librarianName"] == "블루"
    assert profile1["librarianDefaultName"] == "블루"

    # 3. GET /api/v1/members/me 별칭 엔드포인트도 동일하게 작동 확인
    members_me_resp = await client.get("/api/v1/members/me", headers=headers)
    assert members_me_resp.status_code == 200
    profile2 = members_me_resp.json()
    assert profile2["memberId"] == profile1["memberId"]
    assert profile2["librarianType"] == "CAT"
    assert profile2["librarianName"] == "블루"

    # 4. SEA_SLUG 획득 (이름 생략) 및 대표 지정 후 프로필 재조회
    slug_resp = await client.post(
        "/api/v1/librarians", json={"type": "SEA_SLUG"}, headers=headers
    )
    assert slug_resp.status_code == 201
    slug_id = slug_resp.json()["librarianId"]

    await client.patch(f"/api/v1/librarians/{slug_id}/representative", headers=headers)

    updated_profile = (await client.get("/api/v1/members/me", headers=headers)).json()
    assert updated_profile["librarianType"] == "SEA_SLUG"
    assert updated_profile["librarianName"] == "누디"
    assert updated_profile["librarianDefaultName"] == "누디"
