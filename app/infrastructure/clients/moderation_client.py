import httpx
import logging
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModerationClient:

    def __init__(self):
        self.base_url = settings.MODERATION_SERVICE_URL
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))

    async def send_generic_event(self, event_type: str, idempotency_key: str, payload: dict):
        """
        Универсальный метод для воркера
        """
        body = {
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        
        headers = {
            "X-Service-Key": settings.B2B_SERVICE_KEY,
            "Content-Type": "application/json"
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/b2b/events",
            json=body,
            headers=headers
        )
        response.raise_for_status()