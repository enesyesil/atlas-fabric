from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.middleware.auth import api_key_middleware
from api.middleware.rate_limit import limiter
from api.routes.configs import router as configs_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AtlasFabric API",
        description="Historical boundary configurations served via REST API.",
        version="0.1.0",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.middleware("http")(api_key_middleware)
    app.include_router(configs_router)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app
