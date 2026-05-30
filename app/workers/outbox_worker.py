import asyncio
import logging

from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.infrastructure.clients.moderation_client import ModerationClient
from app.infrastructure.clients.b2c_client import B2CClient
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)

class OutboxWorker:
    def __init__(
        self, 
        repo: OutboxRepository, 
        moderation_client: ModerationClient,
        b2c_client: B2CClient,
        max_parallel: int = 5
    ):
        self.repo = repo
        self.running = True
        self.semaphore = asyncio.Semaphore(max_parallel)
        
        self.moderation_client = moderation_client
        self.b2c_client = b2c_client

    async def process_event(self, event: OutboxEvent):
        async with self.semaphore:
            try:
                if event.destination_service == "moderation":
                    # Вызываем универсальный метод клиента
                    await self.moderation_client.send_generic_event(
                        event_type=event.event_type,
                        idempotency_key=event.idempotency_key,
                        payload=event.payload
                    )
                elif event.destination_service == "b2c":
                    await self.b2c_client.send(event.payload)
                
                await self.repo.mark_as_sent(event.id)
            except Exception:
                logger.exception("Failed to process outbox event %s", event.id)
                await self.repo.increment_retry(event.id)

    async def run(self):
        logger.info("Outbox worker started")
        while self.running:
            try:
                events = await self.repo.fetch_pending_events(limit=10)
                
                if not events:
                    await asyncio.sleep(2) # Увеличиваем интервал, если пусто
                    continue

                # Запускаем обработку батча параллельно
                tasks = [self.process_event(event) for event in events]
                await asyncio.gather(*tasks)

            except Exception:
                logger.exception("Worker loop error")
                await asyncio.sleep(5)
            
            await asyncio.sleep(0.1) # Короткая пауза перед следующим батчем

    def stop(self):
        self.running = False