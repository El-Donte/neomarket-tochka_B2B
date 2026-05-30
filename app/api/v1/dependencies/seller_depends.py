# dependencies/auth.py
from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models.seller import Seller
from app.api.v1.dependencies.security import decode_token
from uuid import UUID

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_seller(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session)
) -> UUID:
    """
    Dependency: получает текущего авторизованного продавца.
    При успехе возвращает его ID.
    """
    seller_id = decode_token(credentials.credentials, expected_type="access")
    if seller_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    
    seller = await session.get(Seller, seller_id)
    if not seller or not seller.is_active:
        raise HTTPException(status_code=401, detail="Seller not found")
    
    return seller_id


async def get_optional_current_seller(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    session: AsyncSession = Depends(get_session)
) -> UUID | None:
    if credentials is None:
        return None

    seller_id = decode_token(credentials.credentials, expected_type="access")
    if seller_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    seller = await session.get(Seller, seller_id)
    if not seller or not seller.is_active:
        raise HTTPException(status_code=401, detail="Seller not found")

    return seller_id


async def require_admin_seller(
    seller_id: UUID = Depends(get_current_seller),
    session: AsyncSession = Depends(get_session)
) -> UUID:
    seller = await session.get(Seller, seller_id)
    if not seller or not seller.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return seller_id
