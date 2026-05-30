from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List

from app.models.sku import SKU, CharacteristicValue
from app.models.invoice import Stock, InvoiceItem
from app.models.product import Product
from app.models.image import Image
from app.models.outbox import OutboxEvent


class SKURepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_product_for_seller(
        self, product_id: UUID, seller_id: UUID
    ) -> Optional[Product]:
        result = await self.session.exec(
            select(Product)
            .where(Product.id == product_id)
            .where(Product.seller_id == seller_id)
        )
        return result.first()
    
    async def get_skus_by_product(
        self, product_id: UUID
    ) -> List[SKU]:
        result = await self.session.exec(
            select(SKU)
            .where(SKU.product_id == product_id)
            .options(selectinload(SKU.characteristics))
            .options(selectinload(SKU.images))
            .options(selectinload(SKU.stock))
            .options(selectinload(SKU.product))
        )

        return list(result.all())

    async def get_sku_for_seller(
        self, sku_id: UUID, seller_id: UUID
    ) -> Optional[SKU]:
        statement = (
            select(SKU)
            .join(Product, SKU.product_id == Product.id)
            .where(SKU.id == sku_id)
            .where(Product.seller_id == seller_id)
            .options(selectinload(SKU.characteristics))
            .options(selectinload(SKU.images))
            .options(selectinload(SKU.stock))
            .options(selectinload(SKU.product)) 
        )
        result = await self.session.exec(statement)
        return result.unique().first()

    async def count_skus_by_product(self, product_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(SKU).where(SKU.product_id == product_id)
        )
        return result.scalar_one()
    
    async def create_sku(self, sku: SKU) -> SKU:
        self.session.add(sku)
        await self.session.flush()
        return sku

    async def save_sku(self, sku: SKU) -> SKU:
        self.session.add(sku)
        return sku

    async def save_product(self, product: Product) -> Product:
        self.session.add(product)
        return product

    async def delete_sku(self, sku: SKU):
        await self.session.delete(sku)

    async def get_stock(self, sku_id: UUID, for_update: bool = False) -> Optional[Stock]:
        statement = select(Stock).where(Stock.sku_id == sku_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.exec(statement)
        return result.first()

    async def create_stock(self, stock: Stock):
        self.session.add(stock)

    async def delete_stock(self, stock: Stock):
        await self.session.delete(stock)

    async def get_total_active_quantity(self, product_id: UUID) -> int:
        """
        Возвращает сумму active_quantity всех SKU заданного товара.
        Если SKU нет или все active_quantity = 0, возвращает 0.
        """
        result = await self.session.execute(
            select(func.coalesce(func.sum(Stock.active_quantity), 0))
            .select_from(SKU)
            .join(Stock, SKU.id == Stock.sku_id)
            .where(SKU.product_id == product_id)
        )
        total = result.scalar_one()
        return total

    async def sku_used_in_invoice(self, sku_id: UUID) -> bool:
        result = await self.session.exec(
            select(InvoiceItem).where(InvoiceItem.sku_id == sku_id)
        )
        return result.first() is not None

    async def get_inventory(self, seller_id: UUID):
        statement = (
            select(SKU, Stock, Product.title)
            .join(Stock, SKU.id == Stock.sku_id)
            .join(Product, SKU.product_id == Product.id)
            .where(Product.seller_id == seller_id)
            .options(selectinload(SKU.characteristics))
            .options(selectinload(SKU.images))
        )
        result = await self.session.exec(statement)
        return result.all()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def refresh(self, obj):
        await self.session.refresh(obj)

    async def get_image_for_seller(
        self, image_id: UUID, seller_id: UUID
    ) -> Optional[Image]:
        result = await self.session.exec(
            select(Image)
            .join(SKU, Image.sku_id == SKU.id)
            .join(Product, SKU.product_id == Product.id)
            .where(Image.id == image_id)
            .where(Product.seller_id == seller_id)
        )
        return result.first()

    async def get_image_by_id(self, image_id: UUID) -> Optional[Image]:
        return await self.session.get(Image, image_id)

    async def add_image(self, image: Image) -> Image:
        self.session.add(image)
        await self.session.flush()
        return image

    async def add_outbox_event(self, event: OutboxEvent) -> None:
        self.session.add(event)

    async def update_image(self, image: Image) -> Image:
        self.session.add(image)
        await self.session.flush()
        return image

    async def delete_image(self, image: Image):
        await self.session.delete(image)
