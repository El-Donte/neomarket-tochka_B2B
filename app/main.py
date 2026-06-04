from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os
from sqlalchemy import text
from sqlmodel import select
from fastapi.staticfiles import StaticFiles
from .database import AsyncSessionLocal, create_db_and_tables, engine
from app.api.v1 import auth, sku, products, invoices, upload
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.services.moderation_sync import sync_blocking_reasons
from app.core.config import settings
from app.api.router import api_router
from app.DTO.error import Error
from app.workers.outbox_worker import OutboxWorker
from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.infrastructure.clients.moderation_client import ModerationClient
from app.infrastructure.clients.b2c_client import B2CClient


scheduler = AsyncIOScheduler()

async def scheduled_sync():
    """Обёртка, создающая новую сессию для каждой синхронизации."""
    async with async_session_factory() as session:
        await sync_blocking_reasons(session)

def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    payload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return payload


async def bootstrap_admin() -> None:
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return

    from app.api.v1.dependencies.security import hash_password
    from app.models.seller import Seller

    async with AsyncSessionLocal() as session:
        result = await session.exec(select(Seller).where(Seller.email == settings.ADMIN_EMAIL))
        seller = result.first()

        if seller:
            changed = False
            if not seller.is_admin:
                seller.is_admin = True
                changed = True
            if not seller.is_active:
                seller.is_active = True
                changed = True
            if changed:
                session.add(seller)
                await session.commit()
            return

        admin = Seller(
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            first_name=settings.ADMIN_FIRST_NAME,
            last_name=settings.ADMIN_LAST_NAME,
            company_name=settings.ADMIN_COMPANY_NAME,
            inn=settings.ADMIN_INN,
            is_active=True,
            is_admin=True,
        )
        session.add(admin)
        await session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("app/static/uploads", exist_ok=True)
    try:
        await create_db_and_tables()
        await bootstrap_admin()
    except Exception as e:
        raise Exception(f"Не удалось создать таблицы {e}")
    
    scheduler.add_job(
        scheduled_sync,
        trigger=IntervalTrigger(minutes=5),  # синхронизация каждые 5 минут
        id="sync_blocking_reasons",
        replace_existing=True,
    )
    scheduler.start()
    
    outbox_repo = OutboxRepository(AsyncSessionLocal)
    worker = OutboxWorker(outbox_repo, ModerationClient(), B2CClient())
    task = asyncio.create_task(worker.run())

    yield

    worker.stop()
    scheduler.shutdown()
    await engine.dispose()

def get_application() ->FastAPI:


    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )

    # Настройка CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8080", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_STR)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=settings.PROJECT_NAME,
            version=settings.VERSION,
            routes=app.routes,
            servers=[
                {"url": "/", "description": "Current host"},
                {"url": "http://localhost:8000", "description": "Local development"},
                {"url": "http://b2b:8000", "description": "Internal service URL (внутри docker compose)"},
                {"url": "https://api.neomarket.local/b2b", "description": "Public API gateway"},
            ],
        )
        schema.setdefault("components", {}).setdefault("schemas", {})["Error"] = Error.model_json_schema()
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            content = exc.detail
        else:
            code_by_status = {
                400: "BAD_REQUEST",
                401: "UNAUTHORIZED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                409: "CONFLICT",
                413: "PAYLOAD_TOO_LARGE",
                415: "UNSUPPORTED_MEDIA_TYPE",
                422: "VALIDATION_ERROR",
            }
            content = error_payload(
                code_by_status.get(exc.status_code, "INTERNAL_ERROR"),
                str(exc.detail or "Request failed"),
            )
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(error_payload("VALIDATION_ERROR", "Validation error", {"errors": exc.errors()})),
        )

    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "Service is running"}
    
    @app.get("/health", include_in_schema=False)
    async def health_check():
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return {"status": "ok", "db": "connected"}
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

    return app

app = get_application()
