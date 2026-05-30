from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from anyio.to_thread import run_sync
from app.models.seller import Seller
from app.DTO.seller import SellerCreate, SellerLogin, TokenResponse, RefreshRequest
from app.api.v1.dependencies.security import hash_password, verify_password, decode_token, create_auth_tokens

router = APIRouter()

@router.post("/register", response_model=TokenResponse, status_code=201)    
async def register_seller(
    seller: SellerCreate,
    session: AsyncSession = Depends(get_session),
):
    statement = select(Seller).where(Seller.email == seller.email)

    result = await session.exec(statement)
    existing_seller = result.first()

    if existing_seller:
        raise HTTPException(status_code=409, detail="Пользователь с таким ИНН уже существует")

    db_seller = Seller(
        first_name=seller.first_name,
        password_hash=hash_password(seller.password),
        last_name=seller.last_name,
        inn=seller.inn,
        middle_name=seller.middle_name,
        company_name=seller.company_name,
        phone=seller.phone,
        email=seller.email
    )

    session.add(db_seller)

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    await session.refresh(db_seller)

    tokens = create_auth_tokens(db_seller.id)
    return tokens

@router.post("/login", response_model=TokenResponse)
async def login_seller(
    seller: SellerLogin,
    session: AsyncSession = Depends(get_session)):
    """
    Авторизация продавца.
    На вход получает ИНН и пароль. 
    При успехе возвращает данные продавца и устанавливает JWT токен в cookie.
    """
    statement = (select(Seller).where((Seller.email == seller.email)))
    result = await session.exec(statement)
    existing_seller = result.first()

    if not existing_seller:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    is_valid = await run_sync(  
        verify_password,
        seller.password,
        existing_seller.password_hash,
    )
    if not is_valid:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    tokens = create_auth_tokens(existing_seller.id)
    return tokens

@router.post("/logout", status_code=204)
async def logout_seller(data: RefreshRequest):
    """
    Выход из аккаунта продавца.
    Удаляет куку с JWT токеном.
    """
    

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest):
    seller_id = decode_token(data.refresh_token, expected_type="refresh")
    if seller_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    return create_auth_tokens(seller_id)
