import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_bot_api_token(
    authorization: str | None = Header(default=None),
) -> None:
    settings = get_settings()

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization.partition(" ")

    is_valid_scheme = scheme.lower() == "bearer"
    expected_token = settings.BOT_API_TOKEN
    is_valid_token = bool(expected_token) and secrets.compare_digest(token, expected_token)

    if not is_valid_scheme or not is_valid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot API token",
        )
