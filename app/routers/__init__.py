from app.routers.auth import router as auth_router
from app.routers.books import router as books_router
from app.routers.health import router as health_router
from app.routers.librarians import router as librarians_router
from app.routers.reading_sessions import router as reading_sessions_router
from app.routers.records import router as records_router
from app.routers.reports import router as reports_router
from app.routers.scraps import router as scraps_router
from app.routers.search import router as search_router
from app.routers.shelves import router as shelves_router
from app.routers.terms import router as terms_router
from app.routers.users import router as users_router

__all__ = [
    "auth_router",
    "users_router",
    "terms_router",
    "health_router",
    "search_router",
    "shelves_router",
    "books_router",
    "scraps_router",
    "librarians_router",
    "records_router",
    "reading_sessions_router",
    "reports_router",
]
