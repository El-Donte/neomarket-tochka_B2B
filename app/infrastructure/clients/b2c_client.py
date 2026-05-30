import logging

logger = logging.getLogger(__name__)


class B2CClient:
    async def send(self, payload: dict):
        logger.info("[B2CClient] Event sent: %s", payload)
