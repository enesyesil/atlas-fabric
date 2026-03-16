import os

from fastapi import HTTPException, Request, status


async def api_key_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    secret = os.environ.get("API_SECRET_KEY", "changeme")

    if not api_key or api_key != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )

    return await call_next(request)
