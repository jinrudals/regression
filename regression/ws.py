from typing import Self
import websockets
import websockets.client
import asyncio
import json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class Websocket:
    instance = None

    def __new__(cls) -> Self:
        if cls.instance is None:
            instance = super().__new__(cls)
            cls.instance = instance
            logger.debug("Creating Websocket instance")
        print("Get Websocket instance")
        return cls.instance

    @classmethod
    async def create(cls):

        instance = cls()
        instance.connection = await websockets.client.connect("ws://localhost:8023/backend1")

        await asyncio.ensure_future(instance.start_listening())
        return instance

    async def start_listening(self):
        async for message in self.connection:
            await self.handle_message(message)

    async def handle_message(self, message):
        from modeling.models import Trial
        msg = json.loads(message)
        print(f"Received message: {message}")
        item = await Trial.objects.aget(pk=msg.get("pk"))
        item.status = "running"
        await item.asave()
        # Add your message handling logic here
