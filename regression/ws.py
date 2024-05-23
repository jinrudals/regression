from typing import Self
import websockets
import websockets.client
import asyncio
import json
import logging
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class Websocket:
    instance = None

    def __new__(cls) -> Self:
        if cls.instance is None:
            instance = super().__new__(cls)
            cls.instance = instance
            logger.debug("Creating Websocket instance")
        logger.info("Get Websocket Instacne")
        return cls.instance

    @classmethod
    async def create(cls):

        instance = cls()
        instance.connection = await websockets.client.connect("ws://localhost:8023/backend1")

        await asyncio.ensure_future(instance.start_listening())
        return instance

    async def start_listening(self):
        try:
            async for message in self.connection:
                await self.handle_message(message)
        except:
            self.create()

    async def handle_message(self, message):
        from modeling.models import Trial
        from modeling.serializers import Trial as ter
        msg = json.loads(message)
        logger.info(f"Received message: {message}")
        item = await Trial.objects.aget(pk=msg.get("pk"))
        item.status = "running"

        await item.asave()

        logger.debug(f"Item({item.pk}) has been running status")
        channel = get_channel_layer()

        ser = await sync_to_async(ter)(item)
        data = await sync_to_async(lambda: ser.data)()

        project = data.get('project')
        build = data.get('BUILD_NUMBER')
        logger.debug(f"Item({item.pk}) has been serialized")
        await channel.group_send(
            f'{project}_{build}',
            {
                'type': f"messaging",
                "message": json.dumps(data)
            }
        )
        logger.debug(f"Item({item.pk}) has been passed to jenkins")
