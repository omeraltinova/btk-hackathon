"""FastAPI app entrypoint. Wires routers and middleware; no business logic here."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.routers import auth, chat, family, insights, receipts, transactions


def create_app() -> FastAPI:
    """App factory — keeps testability easy (each test gets its own app/client)."""
    settings = get_settings()

    app = FastAPI(
        title="Cüzdan Koçu API",
        version=__version__,
        description="Türk aileleri için proaktif AI finans koçu — backend.",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
    )

    # CORS — frontend ve API ayrı portlarda; dev'de wide, prod'da explicit list.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers (Day 1: stub'lar, route içermez)
    app.include_router(auth.router)
    app.include_router(transactions.router)
    app.include_router(receipts.router)
    app.include_router(chat.router)
    app.include_router(insights.router)
    app.include_router(family.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Liveness probe — used by docker-compose healthcheck and SETUP.md verification."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
