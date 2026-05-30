from uuid import UUID
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
import logging

from app.models.product import Product, ProductStatus
from app.models.sku import SKU, CharacteristicValue
from app.models.invoice import Stock
from app.DTO.product import ProductCreate, ProductUpdate, ProductDashboardItem
from app.DTO.sku import SKUCreate
from app.models.image import Image
from app.models.outbox import OutboxEvent
from app.DTO.image import ImageCreate, ImageResponse, ImageUpdate, ImageAttachRequest
from app.infrastructure.repositories.product_repository import ProductRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.infrastructure.repositories.outbox_repository import OutboxRepository

logger = logging.getLogger(__name__)

class ProductService:

    def __init__(self, repo: ProductRepository, category_repo: CategoryRepository, outbox_repo: OutboxRepository):
        self.repo = repo
        self.category_repo = category_repo
        self.outbox_repo = outbox_repo

    async def create_product(self, product_in: ProductCreate, seller_id: UUID) -> Product:
        import uuid
        category = self.category_repo.get_by_id(product_in.category_id, True)
        if not category:
            raise HTTPException(status_code=400, detail={"code":"INVALID_REQUEST", "message": "Category not found"})

        product_data = product_in.model_dump(exclude={"characteristics", "images"})
        if not product_data.get("slug"):
            product_data["slug"] = f"{product_in.title.lower().replace(' ', '-')}-{str(uuid.uuid4())[:8]}"

        new_product = Product(
            **product_data,
            seller_id=seller_id,
            status=ProductStatus.CREATED,
            is_deleted=False,
        )
        
        if product_in.images:
            new_product.images = [
                Image(url=str(img.url), ordering=img.ordering)
                for img in product_in.images
            ]
            
        return await self.repo.create(new_product)

    async def get_product(self, product_id: UUID) -> Product:
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")
        return product

    async def update_product(
        self,
        product_id: UUID,
        product_in: ProductUpdate,
        seller_id: UUID,
    ) -> Product:
        product = await self.get_product(product_id)

        if product.seller_id != seller_id:
            raise HTTPException(status_code=403)

        if product.status == ProductStatus.HARD_BLOCKED:
            raise HTTPException(status_code=403, detail="Product is hard blocked and cannot be edited")
        
        data = product_in.model_dump(exclude_unset=True)
        
        if "characteristics" in data:
            data.pop("characteristics")

        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            product.status = ProductStatus.ON_MODERATION

        for key, value in data.items():
            setattr(product, key, value)

        return await self.repo.update(product)
    
    async def delete_product(self, product_id: UUID, seller_id: UUID) -> None:
        product = await self.get_product(product_id)
        if product.seller_id != seller_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if product.is_deleted:
            raise HTTPException(status_code=400, detail="Product already deleted")
        
        skus = await self.repo.get_skus_by_product(product.id)
        sku_ids = [s.id for s in skus]
        
        product.is_deleted = True
        self.repo.session.add(product)
        
        await self.outbox_repo.add(
            OutboxEvent(
                destination_service="moderation",
                event_type="PRODUCT_DELETED",
                aggregate_type="product",
                aggregate_id=product.id,
                idempotency_key=f"prod_del_{product.id}",
                payload={"product_id": str(product.id)}
            ),
            session=self.repo.session
        )

        await self.outbox_repo.add(
            OutboxEvent(
                destination_service="b2c",
                event_type="OUT_OF_STOCK",
                aggregate_type="product",
                aggregate_id=product.id,
                idempotency_key=f"out_of_stock_{product.id}",
                payload={"product_id": str(product.id), "seller_id": str(seller_id)}
            ),
            session=self.repo.session
        )

        await self.repo.commit()

    async def list_my_products(
        self,
        seller_id: UUID,
        limit: int,
        offset: int,
        status_filter: Optional[str],
        include_deleted: bool = False,
    ):
        items, total = await self.repo.get_paginated(seller_id, limit, offset, status_filter, include_deleted)
        return {"items": items, "total_count": total, "limit": limit, "offset": offset}

    async def get_dashboard(
        self,
        seller_id: UUID,
        status: Optional[str],
    ) -> list[ProductDashboardItem]:
        # Implementation left as is for quests
        products = await self.repo.list_by_seller_with_skus(seller_id, status)
        return [
            ProductDashboardItem(
                id=p.id,
                title=p.title,
                status=p.status,
                sku_count=len(p.skus),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in products
        ]

    async def submit_for_moderation(self, product_id: UUID, seller_id: UUID) -> Product:
        db_product = await self.repo.get_by_id_with_skus(product_id, seller_id)
        if not db_product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        if not db_product.skus:
            raise HTTPException(
                status_code=400,
                detail="Нельзя отправить товар на модерацию без SKU",
            )
        
        db_product.status = ProductStatus.ON_MODERATION
        db_product.updated_at = datetime.now(timezone.utc)

        return await self.repo.save(db_product)

    async def get_skus_by_product(self, product_id: UUID, seller_id: UUID) -> List[SKU]:
        product = await self.repo.get_by_id(product_id)
        if not product or product.seller_id != seller_id:
            raise HTTPException(status_code=404, detail="Товар не найден")
        return await self.repo.get_skus_by_product(product_id)
    
    async def add_product_image(
        self,
        product_id: UUID,
        image_in: ImageAttachRequest,
        seller_id: UUID,
    ) -> Image:
        product = await self.get_product(product_id)
        if product.seller_id != seller_id:
            raise HTTPException(status_code=403)

        if image_in.image_id:
            image = await self.repo.get_product_image(image_in.image_id)
            if not image:
                raise HTTPException(status_code=404, detail="Image not found")
            image.product_id = product_id
            image.sku_id = None
            image.ordering = image_in.ordering or 0
            return await self.repo.save_product_image(image)

        if not image_in.url:
            raise HTTPException(status_code=422, detail="Either image_id or url is required")

        new_image = Image(product_id=product_id, url=str(image_in.url), ordering=image_in.ordering or 0)
        return await self.repo.save_product_image(new_image)
    
    async def update_product_image(
        self,
        image_id: UUID,
        image_in: ImageUpdate,
        seller_id: UUID,
    ) -> Image:
        image = await self.repo.get_product_image(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Изображение не найдено")

        product = await self.get_product(image.product_id)
        if product.seller_id != seller_id:
            raise HTTPException(status_code=403)

        update_data = image_in.model_dump(exclude_unset=True)
        if "url" in update_data:
            update_data["url"] = str(update_data["url"])
            
        for key, value in update_data.items():
            setattr(image, key, value)

        return await self.repo.update(image)
    
    async def delete_product_image(
        self,
        image_id: UUID,
        seller_id: UUID,
    ) -> None:
        image = await self.repo.get_product_image(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Изображение не найдено")

        product = await self.get_product(image.product_id)
        if product.seller_id != seller_id:
            raise HTTPException(status_code=403)

        await self.repo.delete_product_image(image)

    async def get_public_products(
        self,
        category_id: Optional[UUID] = None,
        search: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        seller_id: Optional[UUID] = None,
        filters: Optional[dict[str, list[str]]] = None,
        sort: str = "created_desc",
        limit: int = 20,
        offset: int = 0
    ):
        category_ids = None
        if category_id and self.category_repo:
            category_ids = await self.category_repo.get_descendants_ids(category_id)
        elif category_id:
            category_ids = [category_id]

        items, total = await self.repo.get_public_paginated(
            category_ids=category_ids,
            search=search,
            min_price=min_price,
            max_price=max_price,
            seller_id=seller_id,
            filters=filters,
            sort=sort,
            limit=limit,
            offset=offset
        )
        return {"items": items, "total_count": total, "limit": limit, "offset": offset}

    async def get_public_product(self, product_id: UUID):
        product = await self.repo.get_public_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    async def get_public_batch(self, product_ids: List[UUID]):
        return await self.repo.get_public_batch(product_ids)

    async def get_similar_products(self, product_id: UUID, limit: int):
        return await self.repo.get_similar_public(product_id, limit)

    async def get_public_sku(self, sku_id: UUID):
        sku = await self.repo.get_public_sku(sku_id)
        if not sku:
            raise HTTPException(status_code=404, detail="SKU not found")
        return sku
