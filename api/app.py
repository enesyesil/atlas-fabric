import os
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from agents.runtime_env import load_environment
from api.middleware.auth import api_key_middleware
from api.middleware.rate_limit import limiter
from api.routes.configs import router as configs_router


def _require_api_secret() -> None:
    secret = os.environ.get("API_SECRET_KEY", "").strip()
    if not secret or secret == "changeme":
        raise RuntimeError(
            "API_SECRET_KEY must be set to a non-default value before starting the API."
        )


def create_app(*, load_env: bool = True) -> FastAPI:
    if load_env:
        load_environment()

    _require_api_secret()

    from agents.tracing import configure_tracing

    app = FastAPI(
        title="AtlasFabric API",
        description="Historical boundary configurations served via REST API.",
        version="0.1.0",
    )

    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        cast(Any, _rate_limit_exceeded_handler),
    )

    configure_tracing(run_name="api")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.add_middleware(SlowAPIMiddleware)

    app.middleware("http")(api_key_middleware)
    app.include_router(configs_router)

    @app.get("/health", tags=["health"])
    @limiter.exempt
    async def health():
        return {"status": "ok"}

    return app
