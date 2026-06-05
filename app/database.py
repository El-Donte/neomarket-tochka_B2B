from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.product import Product
from app.models.category import Category
from app.models.sku import SKU
from app.models.invoice import Stock, Invoice, InvoiceItem
from app.models.seller import Seller
from app.models.sku import CharacteristicValue
from app.models.image import Image
from app.models.idempotency import IdempotencyKey
from app.models.outbox import OutboxEvent
from app.models.blocking_reason import BlockingReason

engine = create_async_engine(
    settings.DATABASE_URL_B2B,
    echo=True,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def create_db_and_tables():
    """Создать все таблицы при старте"""
    from sqlmodel import SQLModel
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
