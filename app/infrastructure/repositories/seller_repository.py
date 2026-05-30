from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seller import Seller
from app.DTO.seller import SellerUpdate


class SellerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_seller_id(self, seller_id: int) -> Seller | None:
        result = await self.db.execute(
            select(Seller).where(Seller.id == seller_id)
        )
        return result.scalar_one_or_none()

    async def update(self, seller: Seller, data: SellerUpdate) -> Seller:
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(seller, field, value)

        await self.db.commit()
        await self.db.refresh(seller)
        return seller

    async def delete(self, seller: Seller) -> None:
        seller.is_active = False
        self.db.add(seller)
        await self.db.commit()
