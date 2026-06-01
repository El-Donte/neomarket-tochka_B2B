from uuid import UUID
from datetime import datetime, timezone
from fastapi import HTTPException, status
from typing import Optional

from app.models.invoice import Invoice, InvoiceItem, Stock
from app.DTO.invoice import InvoiceCreate, InvoiceAcceptRequest
from app.infrastructure.repositories.invoice_repository import InvoiceRepository
from app.infrastructure.repositories.sku_repository import SKURepository
from app.models.product import ProductStatus


class InvoiceService:

    def __init__(self, repo: InvoiceRepository, sku_repo: SKURepository):
        self.repo = repo
        self.sku_repo = sku_repo

    async def list_invoices(self, seller_id: UUID, limit: int, offset: int, status_filter: Optional[str] = None):
        return await self.repo.list_invoices(seller_id, limit, offset, status_filter)

    async def get_invoice(self, invoice_id: UUID, seller_id: UUID):
        invoice = await self.repo.get_by_id(invoice_id)
        if not invoice or invoice.seller_id != seller_id:
            raise HTTPException(status_code=404, detail="Накладная не найдена")
        return invoice

    async def create_invoice(self, invoice_in: InvoiceCreate, seller_id: UUID):
        if len(invoice_in.items) == 0:
            raise HTTPException(status_code=400, detail="empty list of invoice items")
        
        valid_items = []
        for skus in invoice_in.items:
            sku_db = await self.sku_repo.get_sku_for_seller(skus.sku_id, seller_id)

            if sku_db is None:
                raise HTTPException(status_code=403, detail="Access denied")
            
            if sku_db.product.status != ProductStatus.MODERATED:
                raise HTTPException(status_code=400, detail="Not moderated product")
            
            valid_items.append(skus)

        invoice = Invoice(
            seller_id=seller_id,
            status="CREATED"
        )
        await self.repo.create_invoice(invoice)

        invoice_items = [
            InvoiceItem(
                invoice_id=invoice.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
            )
            for item in valid_items
        ]

        await self.repo.add_items(invoice_items)
        await self.repo.commit()
        return await self.repo.get_by_id(invoice.id)

    async def delete_invoice(self, invoice_id: UUID, seller_id: UUID):
        invoice = await self.repo.get_by_id(invoice_id)
        if not invoice or invoice.seller_id != seller_id:
            raise HTTPException(status_code=404, detail="Накладная не найдена")
        
        if invoice.status != "CREATED":
            raise HTTPException(status_code=409, detail="Нельзя удалить принятую накладную")
        
        await self.repo.delete(invoice)
        await self.repo.commit()

    async def accept_invoice(self, invoice_id: UUID, accept_in: Optional[InvoiceAcceptRequest], accepted_by: UUID):
        invoice = await self.repo.get_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Накладная не найдена")

        if invoice.status in ["ACCEPTED", "CANCELLED"]:
            raise HTTPException(
                status_code=409,
                detail=f"Накладная уже {invoice.status}",
            )

        items = await self.repo.get_items(invoice_id)
        if not items:
            raise HTTPException(status_code=400, detail="Накладная пуста")

        # Map for quick access
        items_map = {item.id: item for item in items}
        
        accepted_at = datetime.now(timezone.utc)
        
        try:
            if not accept_in or not accept_in.accepted_items:
                # Accept all
                for item in items:
                    item.accepted_quantity = item.quantity
                    await self.repo.update_stock(item.sku_id, item.quantity)
                invoice.status = "ACCEPTED"
            else:
                # Partial accept
                any_accepted = False
                for acc_item in accept_in.accepted_items:
                    if acc_item.invoice_item_id in items_map:
                        item = items_map[acc_item.invoice_item_id]
                        item.accepted_quantity = acc_item.accepted_quantity
                        await self.repo.update_stock(item.sku_id, acc_item.accepted_quantity)
                        any_accepted = True
                
                invoice.status = "PARTIALLY_ACCEPTED" if any_accepted else "CANCELLED"

            invoice.accepted_at = accepted_at
            invoice.accepted_by = accepted_by
            invoice.updated_at = accepted_at
            
            await self.repo.save(invoice)
            await self.repo.commit()
            return await self.repo.get_by_id(invoice.id)

        except Exception as e:
            await self.repo.rollback()
            raise HTTPException(status_code=500, detail=str(e))