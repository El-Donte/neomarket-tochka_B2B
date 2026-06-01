from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.database import get_session
from app.api.v1.dependencies.seller_depends import get_current_seller, require_admin_seller
from app.DTO.invoice import (
    InvoiceCreate, 
    InvoiceRead, 
    InvoicePaginatedResponse, 
    InvoiceAcceptRequest
)
from app.infrastructure.repositories.invoice_repository import InvoiceRepository
from app.application.services.invoice_service import InvoiceService
from app.infrastructure.repositories.sku_repository import SKURepository


router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_session),
) -> InvoiceService:
    return InvoiceService(InvoiceRepository(session), SKURepository(session))


@router.get("", response_model=InvoicePaginatedResponse)
async def list_invoices(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    seller_id: UUID = Depends(get_current_seller),
    service: InvoiceService = Depends(get_service),
):
    items, total_count = await service.list_invoices(seller_id, limit, offset, status)
    return InvoicePaginatedResponse(
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )


@router.post("", response_model=InvoiceRead, status_code=201)
async def create_invoice(
    invoice_in: InvoiceCreate,
    seller_id: UUID = Depends(get_current_seller),
    service: InvoiceService = Depends(get_service),
):
    return await service.create_invoice(invoice_in, seller_id)


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: InvoiceService = Depends(get_service),
):
    return await service.get_invoice(invoice_id, seller_id)


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: InvoiceService = Depends(get_service),
):
    await service.delete_invoice(invoice_id, seller_id)


@router.post("/{invoice_id}/accept", response_model=InvoiceRead)
async def accept_invoice(
    invoice_id: UUID,
    accept_in: Optional[InvoiceAcceptRequest] = None,
    seller_id: UUID = Depends(require_admin_seller),
    service: InvoiceService = Depends(get_service),
):
    return await service.accept_invoice(invoice_id, accept_in, seller_id)
