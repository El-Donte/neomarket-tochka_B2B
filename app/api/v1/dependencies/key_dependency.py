from fastapi import Header, HTTPException
from app.core.config import settings


async def verify_service_key(
    x_service_key: str = Header(..., alias="X-Service-Key"),
):
    if x_service_key != settings.B2B_SERVICE_KEY:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Invalid service key"},
        )
