from sqlmodel import select, or_, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, Sequence, List

from app.models.product import Product, ProductStatus
from app.models.sku import SKU, CharacteristicValue
from app.models.invoice import Stock, InvoiceItem
from app.models.image import Image
from app.models.outbox import OutboxEvent


class ProductRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_paginated(
        self, 
        seller_id: UUID, 
        limit: int, 
        offset: int, 
        status: Optional[str] = None, 
        include_deleted: bool = False
    ) -> (Sequence[Product], int):
        query = select(Product).where(Product.seller_id == seller_id)
        
        if not include_deleted:
            query = query.where(Product.is_deleted == False)
        if status:
            query = query.where(Product.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.exec(count_query)

        query = query.limit(limit).offset(offset).options(
            selectinload(Product.images),
            selectinload(Product.skus)
        )
        result = await self.session.exec(query)
        return result.all(), total.one()

    async def create(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.commit()
        return await self.get_by_id(product.id)

    async def get_by_id(self, product_id: UUID) -> Optional[Product]:
        result = await self.session.exec(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.images), 
                selectinload(Product.skus).selectinload(SKU.images),
                selectinload(Product.skus).selectinload(SKU.characteristics),
                selectinload(Product.skus).selectinload(SKU.stock)
            )
        )
        return result.first()
    
    async def update(self, product: Product) -> Product:
        await self.session.commit()
        return await self.get_by_id(product.id)

    async def get_by_id_with_skus(self, product_id: UUID, seller_id: UUID) -> Optional[Product]:
        result = await self.session.exec(
            select(Product)
            .where(Product.id == product_id)
            .where(Product.seller_id == seller_id)
            .options(selectinload(Product.skus))
        )
        return result.first()

    async def list_by_seller_with_skus(
        self,
        seller_id: UUID,
        status: Optional[str] = None,
    ) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.seller_id == seller_id)
            .options(selectinload(Product.skus))
        )
        if status:
            statement = statement.where(Product.status == status)

        result = await self.session.exec(statement)
        return result.all()

    async def save(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.commit()
        return await self.get_by_id(product.id)

    async def get_skus_by_product(self, product_id: UUID) -> List[SKU]:
        result = await self.session.exec(
            select(SKU)
            .where(SKU.product_id == product_id)
            .options(
                selectinload(SKU.images),
                selectinload(SKU.characteristics),
                selectinload(SKU.stock)
            )
        )
        return list(result.all())

    # ---------- Public Catalog Methods ----------

    async def get_public_paginated(
        self,
        category_ids: Optional[List[UUID]] = None,
        search: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        seller_id: Optional[UUID] = None,
        filters: Optional[dict[str, list[str]]] = None,
        sort: str = "created_desc",
        limit: int = 20,
        offset: int = 0
    ):
        query = select(Product).where(
            Product.status == ProductStatus.MODERATED,
            Product.is_deleted == False
        )
        
        # Only show products with SKUs that have stock
        query = query.join(SKU).join(Stock).where(Stock.active_quantity > 0)

        if category_ids:
            query = query.where(Product.category_id.in_(category_ids))
        if seller_id:
            query = query.where(Product.seller_id == seller_id)
        if search:
            query = query.where(or_(
                Product.title.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%")
            ))
        
        if min_price is not None:
            query = query.where(SKU.price >= min_price)
        if max_price is not None:
            query = query.where(SKU.price <= max_price)
        if filters:
            for name, values in filters.items():
                if not values:
                    continue
                matching_products = (
                    select(SKU.product_id)
                    .join(CharacteristicValue, CharacteristicValue.sku_id == SKU.id)
                    .where(
                        CharacteristicValue.name == name,
                        CharacteristicValue.value.in_(values),
                    )
                )
                query = query.where(Product.id.in_(matching_products))

        if sort == "price_asc":
            query = query.order_by(asc(SKU.price))
        elif sort == "price_desc":
            query = query.order_by(desc(SKU.price))
        elif sort == "popular":
            # Just created_desc for now
            query = query.order_by(desc(Product.created_at))
        else:
            query = query.order_by(desc(Product.created_at))

        query = query.distinct()

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.exec(count_query)

        query = query.limit(limit).offset(offset).options(
            selectinload(Product.images),
            selectinload(Product.skus).selectinload(SKU.images),
            selectinload(Product.skus).selectinload(SKU.stock)
        )
        result = await self.session.exec(query)
        
        products = result.all()
        # Add min_price and cover_image manually if needed by DTO
        # But DTO can handle it if we load correctly.
        return products, total.one()

    async def get_public_by_id(self, product_id: UUID) -> Optional[Product]:
        result = await self.session.exec(
            select(Product)
            .join(SKU)
            .join(Stock)
            .where(
                Product.id == product_id,
                Product.status == ProductStatus.MODERATED,
                Product.is_deleted == False,
                Stock.active_quantity > 0
            )
            .options(
                selectinload(Product.images),
                selectinload(Product.skus).selectinload(SKU.images),
                selectinload(Product.skus).selectinload(SKU.characteristics),
                selectinload(Product.skus).selectinload(SKU.stock)
            )
        )
        return result.first()

    async def get_public_batch(self, product_ids: List[UUID]) -> List[Product]:
        result = await self.session.exec(
            select(Product)
            .join(SKU)
            .join(Stock)
            .where(
                Product.id.in_(product_ids),
                Product.status == ProductStatus.MODERATED,
                Product.is_deleted == False,
                Stock.active_quantity > 0
            )
            .distinct()
            .options(
                selectinload(Product.images),
                selectinload(Product.skus).selectinload(SKU.images),
                selectinload(Product.skus).selectinload(SKU.characteristics),
                selectinload(Product.skus).selectinload(SKU.stock)
            )
        )
        return list(result.all())

    async def get_similar_public(self, product_id: UUID, limit: int) -> List[Product]:
        product = await self.get_by_id(product_id)
        if not product:
            return []
        
        result = await self.session.exec(
            select(Product)
            .join(SKU)
            .join(Stock)
            .where(
                Product.category_id == product.category_id,
                Product.id != product_id,
                Product.status == ProductStatus.MODERATED,
                Product.is_deleted == False,
                Stock.active_quantity > 0
            )
            .distinct()
            .limit(limit)
            .options(
                selectinload(Product.images),
                selectinload(Product.skus).selectinload(SKU.stock),
            )
        )
        return list(result.all())

    async def get_public_sku(self, sku_id: UUID) -> Optional[SKU]:
        result = await self.session.exec(
            select(SKU)
            .join(Product)
            .where(
                SKU.id == sku_id,
                Product.status == ProductStatus.MODERATED,
                Product.is_deleted == False
            )
            .options(
                selectinload(SKU.images),
                selectinload(SKU.characteristics),
                selectinload(SKU.stock)
            )
        )
        return result.first()

    # ---------- Common Methods ----------

    async def get_sku(self, sku_id: UUID) -> Optional[SKU]:
        return await self.session.get(SKU, sku_id)

    async def create_sku(self, sku: SKU) -> SKU:
        self.session.add(sku)
        await self.session.flush()
        return sku

    async def save_sku(self, sku: SKU) -> SKU:
        self.session.add(sku)
        await self.session.commit()
        await self.session.refresh(sku)
        return sku

    async def delete_sku(self, sku: SKU) -> None:
        await self.session.delete(sku)

    async def get_stock(self, sku_id: UUID) -> Optional[Stock]:
        result = await self.session.exec(
            select(Stock).where(Stock.sku_id == sku_id)
        )
        return result.first()

    async def create_stock(self, stock: Stock) -> None:
        self.session.add(stock)

    async def delete_stock(self, stock: Stock) -> None:
        await self.session.delete(stock)

    async def get_invoice_item_by_sku(self, sku_id: UUID) -> Optional[InvoiceItem]:
        result = await self.session.exec(
            select(InvoiceItem).where(InvoiceItem.sku_id == sku_id)
        )
        return result.first()

    async def get_product_image(self, image_id: UUID) -> Optional[Image]:
        result = await self.session.exec(select(Image).where(Image.id == image_id))
        return result.first()

    async def save_product_image(self, image: Image) -> Image:
        self.session.add(image)
        await self.session.commit()
        await self.session.refresh(image)
        return image

    async def add_outbox_event(self, event: OutboxEvent) -> None:
        self.session.add(event)

    async def delete_product_image(self, image: Image) -> None:
        await self.session.delete(image)
        await self.session.commit()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
