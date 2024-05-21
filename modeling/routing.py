from django.urls import re_path
from .consumer import Consumer

websocket_urlpatterns = [
    re_path(r'ws/(?P<room_name>\w+)/$', Consumer.as_asgi()),
]
