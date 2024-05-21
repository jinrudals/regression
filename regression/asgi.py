"""
ASGI config for regression project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
import django
import asyncio
import threading
import logging
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.conf import settings
from modeling.routing import websocket_urlpatterns
from .ws import Websocket

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'regression.settings')
django.setup()


async def start_websocket():
    logger.debug("Start websocket")
    websocket_instance = await Websocket.create()
    websocket_instance.start_listening()


def run_in_thread():
    loop: asyncio.AbstractEventLoop = settings.LOOP
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_websocket())


# Ensure this only runs once during server startup
if 'RUN_MAIN' in os.environ:
    thread = threading.Thread(target=run_in_thread)
    thread.start()


# application = temp(get_asgi_application)
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(websocket_urlpatterns),
})
