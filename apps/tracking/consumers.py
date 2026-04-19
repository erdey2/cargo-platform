import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.gis.geos import Point
from apps.tracking.models import DriverLocation
from apps.drivers.models import DriverProfile


class DriverLocationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        self.shipment_id = self.scope["url_route"]["kwargs"]["shipment_id"]
        self.group_name = f"shipment_{self.shipment_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)

        lat = data.get("lat")
        lng = data.get("lng")

        await self.save_location(lat, lng)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "send_location",
                "lat": lat,
                "lng": lng,
            }
        )

    async def send_location(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def save_location(self, lat, lng):
        driver = DriverProfile.objects.get(user=self.user)
        DriverLocation.objects.update_or_create(
            driver=driver,
            defaults={"location": Point(lng, lat)}
        )