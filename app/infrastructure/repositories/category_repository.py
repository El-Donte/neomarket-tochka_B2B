from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import update, func
from uuid import UUID
from typing import Optional, List, Sequence

from app.models.category import Category


class CategoryRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def get_by_id(self, category_id: UUID, include_children: bool = False) -> Optional[Category]:
        query = select(Category).where(Category.id == category_id)
        if include_children:
            query = query.options(selectinload(Category.children))

        result = await self.session.execute(query)

        return result.scalar_one_or_none()
    
    async def get_by_ids(self, ids: List[UUID]) -> Sequence[Category]:
        query = select(Category).where(Category.id.in_(ids))
        result = await self.session.exec(query)
        return result.all()

    async def list(
        self,
        parent_id: Optional[UUID] = None,
        only_root: bool = False,
    ) -> List[Category]:

        statement = select(Category)

        if only_root:
            statement = statement.where(Category.parent_id.is_(None))
        elif parent_id is not None:
            statement = statement.where(Category.parent_id == parent_id)

        result = await self.session.exec(statement)
        return result.all()
    
    async def save(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete(self, category: Category):
        await self.session.delete(category)
        await self.session.commit()

    async def get_all_for_tree(self) -> Sequence[Category]:
        result = await self.session.exec(
            select(Category)
            .where(Category.is_active == True))
        return result.all()
    
    async def update(self, category: Category) -> Category:
        await self.session.commit()
        await self.session.refresh(category)
        return category
    
    async def get_existing_slugs(self) -> set[str]:
        result = await self.session.exec(select(Category.slug))
        return set(result.all())
    
    async def has_products(self, category_id: UUID) -> bool:
        from app.models.product import Product
        query = select(Product).where(Product.category_id == category_id).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def get_descendants_ids(self, category_id: UUID) -> List[UUID]:
        category = await self.get_by_id(category_id)
        if not category:
            return []
        
        prefix = f"{category.path}/{category.id}".strip("/")
        statement = select(Category.id).where(
            (Category.path == prefix) | (Category.path.like(f"{prefix}/%"))
        )
        result = await self.session.exec(statement)
        ids = list(result.all())
        ids.append(category_id)
        return ids

    async def update_descendants_path(self, old_full_path: str, new_full_path: str, level_delta: int):
        """
        Массово обновляет path и level у всех категорий, чей путь начинается с old_full_path.
        Например: переместили папку, нужно во всех вложенных путях заменить старый префикс на новый.
        """

        query = (
            update(Category)
            .where(Category.path.like(f"{old_full_path}%") | (Category.path == old_full_path))
            .values(
                path=func.replace(Category.path, old_full_path, new_full_path),
                level=Category.level + level_delta
            )
        )
        await self.session.exec(query)