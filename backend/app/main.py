"""FastAPI app entrypoint. Wires routers and middleware; no business logic here."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.routers import (
    auth,
    categories,
    chat,
    conversations,
    family,
    insights,
    memory,
    receipts,
    saving_goals,
    subscriptions,
    transactions,
)


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

    @app.exception_handler(RequestValidationError)
    def validation_error_handler(
        _request: object,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Gönderilen bilgileri kontrol eder misin?"},
        )

    # Routers
    app.include_router(auth.router)
    app.include_router(categories.router)
    app.include_router(transactions.router)
    app.include_router(subscriptions.router)
    app.include_router(receipts.router)
    app.include_router(saving_goals.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(memory.router)
    app.include_router(insights.router)
    app.include_router(family.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Liveness probe — used by docker-compose healthcheck and SETUP.md verification."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
