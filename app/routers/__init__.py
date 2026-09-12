from app.routers.books import router as books_router
from app.routers.health import router as health_router
from app.routers.librarians import router as librarians_router
from app.routers.records import router as records_router
from app.routers.scraps import router as scraps_router
from app.routers.search import router as search_router
from app.routers.shelves import router as shelves_router

__all__ = [
    "health_router",
    "search_router",
    "shelves_router",
    "books_router",
    "scraps_router",
    "librarians_router",
    "records_router",
]
