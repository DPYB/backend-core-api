from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """애플리케이션 비즈니스 기본 예외"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


# --- 400 Bad Request ---
class InvalidSearchParameterException(AppException):
    def __init__(self, message: str = "검색 파라미터가 올바르지 않습니다."):
        super().__init__(
            status.HTTP_400_BAD_REQUEST, "INVALID_SEARCH_PARAMETER", message
        )


class InvalidBookDataException(AppException):
    def __init__(self, message: str = "도서 데이터가 올바르지 않습니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_BOOK_DATA", message)


class InvalidFilterParameterException(AppException):
    def __init__(self, message: str = "정렬 또는 필터 파라미터가 올바르지 않습니다."):
        super().__init__(
            status.HTTP_400_BAD_REQUEST, "INVALID_FILTER_PARAMETER", message
        )


class InvalidPageValueException(AppException):
    def __init__(
        self, message: str = "진도 페이지 값은 0 이상 전체 페이지 이하여야 합니다."
    ):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_PAGE_VALUE", message)


class InvalidReorderTargetException(AppException):
    def __init__(self, message: str = "재정렬 대상이 올바르지 않습니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_REORDER_TARGET", message)


class InvalidShelfTargetException(AppException):
    def __init__(self, message: str = "이동할 책장 대상이 올바르지 않습니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_SHELF_TARGET", message)


class InvalidShelfDataException(AppException):
    def __init__(self, message: str = "책장 데이터가 올바르지 않습니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_SHELF_DATA", message)


class DefaultShelfCannotBeDeletedException(AppException):
    def __init__(self, message: str = "기본 책장은 삭제할 수 없습니다."):
        super().__init__(
            status.HTTP_400_BAD_REQUEST, "DEFAULT_SHELF_CANNOT_BE_DELETED", message
        )


class InvalidScrapDataException(AppException):
    def __init__(self, message: str = "스크랩 데이터가 올바르지 않습니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_SCRAP_DATA", message)


class InvalidLibrarianDataException(AppException):
    def __init__(self, message: str = "사서 데이터가 올바르지 않습니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "INVALID_LIBRARIAN_DATA", message)


class TermsNotAgreedException(AppException):
    def __init__(self, message: str = "필수 약관에 모두 동의해야 합니다."):
        super().__init__(status.HTTP_400_BAD_REQUEST, "TERMS_NOT_AGREED", message)


# --- 401 Unauthorized ---
class UnauthorizedException(AppException):
    def __init__(self, message: str = "인증에 실패했습니다."):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", message)


# --- 403 Forbidden ---
class LibraryBookAccessDeniedException(AppException):
    def __init__(self, message: str = "해당 도서에 대한 접근 권한이 없습니다."):
        super().__init__(
            status.HTTP_403_FORBIDDEN, "LIBRARY_BOOK_ACCESS_DENIED", message
        )


class ShelfAccessDeniedException(AppException):
    def __init__(self, message: str = "해당 책장에 대한 접근 권한이 없습니다."):
        super().__init__(status.HTTP_403_FORBIDDEN, "SHELF_ACCESS_DENIED", message)


class ScrapAccessDeniedException(AppException):
    def __init__(self, message: str = "해당 스크랩에 대한 접근 권한이 없습니다."):
        super().__init__(status.HTTP_403_FORBIDDEN, "SCRAP_ACCESS_DENIED", message)


class LibrarianAccessDeniedException(AppException):
    def __init__(self, message: str = "해당 사서에 대한 접근 권한이 없습니다."):
        super().__init__(status.HTTP_403_FORBIDDEN, "LIBRARIAN_ACCESS_DENIED", message)


class GuestReadOnlyModeException(AppException):
    def __init__(
        self,
        message: str = "체험 모드(게스트)에서는 읽기 전용으로만 이용 가능합니다. 변경 작업을 수행하려면 로그인해 주세요.",
    ):
        super().__init__(status.HTTP_403_FORBIDDEN, "GUEST_READONLY_MODE", message)


# --- 429 Too Many Requests ---
class RateLimitExceededException(AppException):
    def __init__(
        self,
        message: str = "요청 횟수 제한을 초과했습니다. 잠시 후 다시 시도해 주세요.",
    ):
        super().__init__(
            status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMIT_EXCEEDED", message
        )


# --- 404 Not Found ---
class LibraryBookNotFoundException(AppException):
    def __init__(self, message: str = "도서를 찾을 수 없습니다."):
        super().__init__(status.HTTP_404_NOT_FOUND, "LIBRARY_BOOK_NOT_FOUND", message)


class ShelfNotFoundException(AppException):
    def __init__(self, message: str = "책장을 찾을 수 없습니다."):
        super().__init__(status.HTTP_404_NOT_FOUND, "SHELF_NOT_FOUND", message)


class ScrapNotFoundException(AppException):
    def __init__(self, message: str = "스크랩을 찾을 수 없습니다."):
        super().__init__(status.HTTP_404_NOT_FOUND, "SCRAP_NOT_FOUND", message)


class LibrarianNotFoundException(AppException):
    def __init__(self, message: str = "사서를 찾을 수 없습니다."):
        super().__init__(status.HTTP_404_NOT_FOUND, "LIBRARIAN_NOT_FOUND", message)


class RepresentativeLibrarianNotSelectedException(AppException):
    def __init__(self, message: str = "대표 사서가 지정되지 않았습니다."):
        super().__init__(
            status.HTTP_404_NOT_FOUND, "REPRESENTATIVE_LIBRARIAN_NOT_SELECTED", message
        )


# --- 409 Conflict ---
class BookAlreadyRegisteredException(AppException):
    def __init__(self, message: str = "이미 서재에 등록된 도서입니다."):
        super().__init__(status.HTTP_409_CONFLICT, "BOOK_ALREADY_REGISTERED", message)


class LibrarianAlreadyOwnedException(AppException):
    def __init__(self, message: str = "이미 보유하고 있는 사서 종류입니다."):
        super().__init__(status.HTTP_409_CONFLICT, "LIBRARIAN_ALREADY_OWNED", message)


class EmailAlreadyExistsException(AppException):
    def __init__(self, message: str = "이미 가입된 이메일입니다."):
        super().__init__(status.HTTP_409_CONFLICT, "EMAIL_ALREADY_EXISTS", message)


# --- 502 Bad Gateway ---
class ExternalApiException(AppException):
    def __init__(
        self, message: str = "외부 도서 검색 API 통신 중 오류가 발생했습니다."
    ):
        super().__init__(status.HTTP_502_BAD_GATEWAY, "EXTERNAL_API_ERROR", message)


# --- 500 Internal Server Error ---
class InternalErrorException(AppException):
    def __init__(self, message: str = "서버 내부 오류가 발생했습니다."):
        super().__init__(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", message
        )


def register_exception_handlers(app: FastAPI) -> None:
    """FastAPI 전역 예외 처리기 등록"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        first_err = exc.errors()[0] if exc.errors() else {}
        loc = first_err.get("loc", [])
        field_name = str(loc[-1]) if loc else "field"
        msg = first_err.get("msg", "입력값이 유효하지 않습니다.")
        path = request.url.path

        if "header" in [str(x) for x in loc] or path.startswith("/api/v1/records"):
            return JSONResponse(
                status_code=422,
                content={"detail": exc.errors()},
            )

        if "search" in path or "isbn" in [str(x) for x in loc]:
            error_code = "INVALID_SEARCH_PARAMETER"
        elif "shelves" in path or "shelf" in [str(x) for x in loc]:
            error_code = "INVALID_SHELF_DATA"
        elif "scraps" in path or "scrap" in [str(x) for x in loc]:
            error_code = "INVALID_SCRAP_DATA"
        elif "librarian" in path:
            error_code = "INVALID_LIBRARIAN_DATA"
        elif any(
            f in [str(x) for x in loc]
            for f in ["sortBy", "sortOrder", "readingStatus", "genre"]
        ):
            error_code = "INVALID_FILTER_PARAMETER"
        else:
            error_code = "INVALID_BOOK_DATA"

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": error_code, "message": f"{field_name}: {msg}"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)

        code_map = {
            400: "INVALID_BOOK_DATA",
            401: "UNAUTHORIZED",
            403: "LIBRARY_BOOK_ACCESS_DENIED",
            404: "LIBRARY_BOOK_NOT_FOUND",
            409: "BOOK_ALREADY_REGISTERED",
            429: "RATE_LIMIT_EXCEEDED",
            502: "EXTERNAL_API_ERROR",
        }
        code = code_map.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": str(exc.detail)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_ERROR",
                "message": "서버 내부 오류가 발생했습니다.",
            },
        )
