import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.gis.geos import Point
from django.core.exceptions import ObjectDoesNotExist
from apps.tracking.models import DriverLocation
from apps.drivers.models import DriverProfile
from apps.shipments.models import Shipment

class DriverLocationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.shipment_id = self.scope["url_route"]["kwargs"]["shipment_id"]

        self.role = await self.get_role()
        self.group_name = f"shipment_{self.shipment_id}_{self.role}"

        authorized = await self.is_authorized()
        if not authorized:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        print(f"CONNECTED: user={self.user.id}, role={self.role}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)

        lat = float(data.get("lat"))
        lng = float(data.get("lng"))

        await self.save_location(lat, lng)

        payload = {
            "event": "driver.location",
            "data": {
                "driver_id": self.user.id,
                "lat": lat,
                "lng": lng
            }
        }

        # broadcast to customer + admin ONLY (driver does not need echo)
        await self.channel_layer.group_send(
            f"shipment_{self.shipment_id}_customer",
            {"type": "send_location", "payload": payload}
        )

        await self.channel_layer.group_send(
            f"shipment_{self.shipment_id}_admin",
            {"type": "send_location", "payload": payload}
        )

    async def send_location(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @sync_to_async
    def get_role(self):
        if self.user.groups.filter(name="drivers").exists():
            return "driver"
        elif self.user.groups.filter(name="admins").exists():
            return "admin"
        return "customer"

    @sync_to_async
    def save_location(self, lat, lng):
        try:
            driver = DriverProfile.objects.get(user=self.user)

            DriverLocation.objects.update_or_create(
                driver=driver,
                defaults={
                    "location": Point(lng, lat, srid=4326)
                }
            )

        except ObjectDoesNotExist:
            print("Driver profile not found")

    @sync_to_async
    def is_authorized(self):
        return Shipment.objects.filter(
            id=self.shipment_id,
            driver__user=self.user
        ).exists() or Shipment.objects.filter(
            id=self.shipment_id,
            customer=self.user
        ).exists()