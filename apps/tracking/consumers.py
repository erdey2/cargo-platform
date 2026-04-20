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
            await self.close(code=4001)  # custom close code
            return

        try:
            self.shipment_id = self.scope["url_route"]["kwargs"]["shipment_id"]
            self.group_name = f"shipment_{self.shipment_id}"

            if not await self.is_authorized():
                await self.close(code=4003)
                return

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )

            await self.accept()

            print(f"CONNECTED: user={self.user.id}, shipment={self.shipment_id}")

        except Exception as e:
            print("CONNECT ERROR:", e)
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

        print(f"DISCONNECTED: {getattr(self, 'group_name', 'unknown')}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            lat = data.get("lat")
            lng = data.get("lng")

            if lat is None or lng is None:
                return

            # Save safely
            await self.save_location(lat, lng)

            # Broadcast
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "send_location",
                    "data": {
                        "lat": lat,
                        "lng": lng,
                    }
                }
            )

        except Exception as e:
            print("RECEIVE ERROR:", e)

    async def send_location(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    # Helpers

    @sync_to_async
    def save_location(self, lat, lng):
        try:
            driver = DriverProfile.objects.get(user=self.user)

            DriverLocation.objects.update_or_create(
                driver=driver,
                defaults={"location": Point(lng, lat)}
            )

        except ObjectDoesNotExist:
            print("Driver profile not found")

    @sync_to_async
    def is_authorized(self):
        """
        Ensure user belongs to this shipment
        (driver OR customer)
        """
        return Shipment.objects.filter(
            id=self.shipment_id
        ).filter(
            driver__user=self.user
        ).exists() or Shipment.objects.filter(
            id=self.shipment_id,
            customer=self.user
        ).exists()