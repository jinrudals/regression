import asyncio
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from regression.ws import Websocket
from . import models


@receiver(post_save, sendr=models.Trial)
async def handle_trial_on_pending(sender, instance: models.Trial, created, **kwargs):
    if instance.status == "pending":
        asyncio.run(send_message("Hello"))


async def send_message(message):
    print("I am here")
    await Websocket().connection.send(str(message))
