from uuid import UUID
from datetime import datetime, timezone
from fastapi import HTTPException, status
from typing import List, Optional
import logging

from app.models.sku import SKU, CharacteristicValue
from app.models.invoice import Stock
from app.DTO.sku import SKUCreate, SKUUpdate
from app.infrastructure.repositories.sku_repository import SKURepository
from app.models.image import Image
from app.models.product import ProductStatus
from app.DTO.image import ImageUpdate, ImageAttachRequest
from app.models.outbox import OutboxEvent
from app.infrastructure.repositories.outbox_repository import OutboxRepository

logger = logging.getLogger(__name__)


class SKUService:

    def __init__(self, repo: SKURepository, outbox_repo: OutboxRepository):
        self.repo = repo
        self.outbox_repo = outbox_repo

    async def create_sku(self, sku_in: SKUCreate, seller_id: UUID) -> SKU:
        product = await self.repo.get_product_for_seller(sku_in.product_id, seller_id)
        if not product:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if product.status == ProductStatus.HARD_BLOCKED:
            raise HTTPException(status_code=403, detail="Товар был безвозвратно забанен")

        db_sku = SKU(
            product_id=sku_in.product_id,
            name=sku_in.name,
            price=sku_in.price,
            discount=sku_in.discount,
            cost_price=sku_in.cost_price,
            article=sku_in.article,
        )

        if sku_in.characteristics:
            db_sku.characteristics = [
                CharacteristicValue(name=c.name, value=c.value)
                for c in sku_in.characteristics
            ]
            
        if sku_in.images:
            db_sku.images = [
                Image(url=str(img.url), ordering=img.ordering)
                for img in sku_in.images
            ]

        needs_moderation = product.status in [ProductStatus.CREATED, ProductStatus.MODERATED, ProductStatus.BLOCKED]

        try:
            await self.repo.create_sku(db_sku)
            await self.repo.create_stock(Stock(sku_id=db_sku.id, stock_quantity=0, active_quantity=0, reserved_quantity=0))
            
            if needs_moderation:
                product.status = ProductStatus.ON_MODERATION
                await self.repo.save_product(product)

                await self.outbox_repo.add(
                    OutboxEvent(
                        destination_service="moderation",
                        event_type="PRODUCT_CREATED",
                        aggregate_type="product",
                        aggregate_id=product.id,
                        idempotency_key = f"prod_edit_{product.id}_{int(datetime.now().timestamp())}", 
                        payload={
                            "product_id": str(product.id),
                            "seller_id": str(seller_id),
                            "category_id": str(product.category_id) if product.category_id else None,
                            "queue_priority": 3,
                            "json_after": self._product_snapshot(product)
                        }
                    ),
                    session=self.repo.session
                )

            await self.repo.commit()
        except Exception as e:
            await self.repo.rollback()
            raise HTTPException(status_code=500, detail=str(e))

        return await self.repo.get_sku_for_seller(db_sku.id, seller_id)

    async def update_sku(self, sku_id: UUID, sku_in: SKUUpdate, seller_id: UUID) -> SKU:
        db_sku = await self.repo.get_sku_for_seller(sku_id, seller_id)
        if not db_sku:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if db_sku.product.status == ProductStatus.HARD_BLOCKED:
            raise HTTPException(status_code=403, detail="Товар был безвозвратно забанен")

        snapshot_before = self._product_snapshot(db_sku.product)

        update_data = sku_in.model_dump(exclude_unset=True)
        
        if "characteristics" in update_data:
            # Simple replace for now
            new_chars = update_data.pop("characteristics")
            if new_chars is not None:
                db_sku.characteristics = [
                    CharacteristicValue(name=c["name"], value=c["value"])
                    for c in new_chars
                ]

        for key, value in update_data.items():
            setattr(db_sku, key, value)

        db_sku.updated_at = datetime.now(timezone.utc)

        needs_moderation = db_sku.product.status in [
            ProductStatus.MODERATED, ProductStatus.BLOCKED
        ]

        if needs_moderation:
            db_sku.product.status = ProductStatus.ON_MODERATION
            db_sku.product.updated_at = db_sku.updated_at
            await self.repo.save_product(db_sku.product)
        
        await self.repo.save_sku(db_sku)

        if needs_moderation:
            await self.outbox_repo.add(
                OutboxEvent(
                    destination_service="moderation",
                    event_type="PRODUCT_EDITED",
                    aggregate_type="product",
                    aggregate_id=db_sku.product.id,
                    idempotency_key=f"prod_edit_{db_sku.product.id}_{datetime.now(timezone.utc).timestamp()}",
                    payload={
                        "product_id": str(db_sku.product.id),
                        "seller_id": str(seller_id),
                        "category_id": str(db_sku.product.category_id),
                        "queue_priority": 3,
                        "json_before": snapshot_before,
                        "json_after": self._product_snapshot(db_sku.product),
                    }
                ),
                session=self.repo.session
            )

        await self.repo.commit()
        return await self.repo.get_sku_for_seller(db_sku.id, seller_id)

    async def get_sku(self, sku_id: UUID, seller_id: UUID) -> SKU:
        db_sku = await self.repo.get_sku_for_seller(sku_id, seller_id)
        if not db_sku:
            raise HTTPException(status_code=404, detail="SKU не найден")
        return db_sku

    async def delete_sku(self, sku_id: UUID, seller_id: UUID):
        db_sku = await self.repo.get_sku_for_seller(sku_id, seller_id)
        if not db_sku:
            raise HTTPException(status_code=403, detail="Access denied")
        
        product = db_sku.product
        
        if product.status == ProductStatus.HARD_BLOCKED:
            raise HTTPException(status_code=403, detail="Товар был безвозвратно забанен")

        stock = await self.repo.get_stock(sku_id)
        if stock and stock.reserved_quantity > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Нельзя удалить SKU с активными резервами ({stock.reserved_quantity} шт)",
            )
        
        skus_count = await self.repo.count_skus_by_product(product.id)
        is_last = (skus_count == 1)
        product_status_before = product.status

        try:
            if stock:
                await self.repo.delete_stock(stock)
            await self.repo.delete_sku(db_sku)

            if is_last and product_status_before == ProductStatus.ON_MODERATION:
                product.status = ProductStatus.CREATED
                await self.repo.save_product(product)

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

            if product_status_before == ProductStatus.MODERATED:
                total_active = await self.repo.get_total_active_quantity(product.id)
                if total_active == 0:
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
        except Exception as e:
            await self.repo.rollback()
            raise e

    async def get_inventory(self, seller_id: UUID):
        results = await self.repo.get_inventory(seller_id)
        return [
            {
                "sku_id": sku.id,
                "sku_name": sku.name,
                "product_title": product_title,
                "price": sku.price,
                "quantity": stock.stock_quantity,
                "active_quantity": stock.active_quantity,
                "reserved_quantity": stock.reserved_quantity,
                "updated_at": stock.updated_at,
            }
            for sku, stock, product_title in results
        ]
    
    async def get_skus_by_product(self, product_id: UUID, seller_id: UUID) -> List[SKU]:
        product = await self.repo.get_product_for_seller(product_id, seller_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден или не принадлежит вам")
        return await self.repo.get_skus_by_product(product_id)
    
    async def add_sku_image(self, sku_id: UUID, image_in: ImageAttachRequest, seller_id: UUID) -> Image:
        sku = await self.repo.get_sku_for_seller(sku_id, seller_id)
        if not sku:
            raise HTTPException(status_code=404, detail="SKU не найден")

        if image_in.image_id:
            db_image = await self.repo.get_image_by_id(image_in.image_id)
            if not db_image:
                raise HTTPException(status_code=404, detail="Image not found")
            db_image.sku_id = sku_id
            db_image.product_id = None
            db_image.ordering = image_in.ordering or 0
        else:
            if not image_in.url:
                raise HTTPException(status_code=422, detail="Either image_id or url is required")
            db_image = Image(sku_id=sku_id, url=str(image_in.url), ordering=image_in.ordering or 0)
        await self.repo.add_image(db_image)
        await self.repo.commit()
        await self.repo.refresh(db_image)
        return db_image

    async def update_sku_image(self, image_id: UUID, image_in: ImageUpdate, seller_id: UUID) -> Image:
        db_image = await self.repo.get_image_for_seller(image_id, seller_id)
        if not db_image:
            raise HTTPException(status_code=404, detail="Изображение не найдено")

        update_data = image_in.model_dump(exclude_unset=True)
        if "url" in update_data:
            update_data["url"] = str(update_data["url"])
            
        for key, value in update_data.items():
            setattr(db_image, key, value)

        await self.repo.update_image(db_image)
        await self.repo.commit()
        await self.repo.refresh(db_image)
        return db_image

    async def delete_sku_image(self, image_id: UUID, seller_id: UUID):
        db_image = await self.repo.get_image_for_seller(image_id, seller_id)
        if not db_image:
            raise HTTPException(status_code=404, detail="Изображение не найдено")

        await self.repo.delete_image(db_image)
        await self.repo.commit()

    def _product_snapshot(self, product) -> dict:
        return {
            "id": str(product.id),
            "title": product.title,
            "description": product.description,
            "category_id": str(product.category_id) if product.category_id else None,
            "status": product.status.value if product.status else None,
            "seller_id": str(product.seller_id),
            "is_deleted": product.is_deleted,
            "slug": product.slug
        }
