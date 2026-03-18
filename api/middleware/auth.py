import os

from fastapi import Request, status
from fastapi.responses import JSONResponse


async def api_key_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    secret = os.environ["API_SECRET_KEY"]

    if not api_key or api_key != secret:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing X-API-Key header"},
        )

    return await call_next(request)
