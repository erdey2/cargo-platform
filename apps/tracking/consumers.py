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

        self.group_name = None

        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return

        try:
            self.shipment_id = self.scope["url_route"]["kwargs"]["shipment_id"]

            self.role = await self.get_role()
            group_name = f"shipment_{self.shipment_id}_{self.role}"

            authorized = await self.is_authorized()
            if not authorized:
                await self.close(code=4003)
                return

            self.group_name = group_name

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )

            await self.accept()

            print(f"CONNECTED: user={self.user.id}, role={self.role}, group={self.group_name}")
            print("USER:", self.user)
            print("ROLE:", self.user.role)
            print("GROUP:", self.group_name)

        except Exception as e:
            print("CONNECT ERROR:", e)
            await self.close()

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

        print(f"DISCONNECTED: {getattr(self, 'group_name', 'no-group')}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            lat = data.get("lat")
            lng = data.get("lng")
            heading = data.get("heading")
            speed = data.get("speed")

            if lat is None or lng is None:
                return

            lat = float(lat)
            lng = float(lng)

            # ONLY DRIVER CAN SEND LOCATION
            if self.role != "driver":
                return

            # Save to DB
            await self.save_location(lat, lng, heading, speed)

            payload = {
                "event": "driver.location",
                "data": {
                    "driver_id": self.user.id,
                    "shipment_id": self.shipment_id,
                    "lat": lat,
                    "lng": lng,
                    "heading": heading,
                    "speed": speed,
                }
            }

            # Broadcast to CUSTOMER
            await self.channel_layer.group_send(
                f"shipment_{self.shipment_id}_customer",
                {"type": "send_location", "payload": payload}
            )

            # Broadcast to ADMIN
            await self.channel_layer.group_send(
                f"shipment_{self.shipment_id}_admin",
                {"type": "send_location", "payload": payload}
            )

        except Exception as e:
            print("RECEIVE ERROR:", e)

    async def send_location(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    # HELPERS
    @sync_to_async
    def get_role(self):
        return getattr(self.user, "role", "customer")

    @sync_to_async
    def save_location(self, lat, lng, heading=None, speed=None):
        try:
            driver = DriverProfile.objects.get(user=self.user)

            DriverLocation.objects.update_or_create(
                driver=driver,
                defaults={
                    "location": Point(lng, lat, srid=4326),
                    "heading": heading,
                    "speed": speed,
                    "is_online": True,
                }
            )

        except ObjectDoesNotExist:
            print("Driver profile not found")

    @sync_to_async
    def is_authorized(self):
        print("AUTH DEBUG:")
        print("USER:", self.user)
        print("ROLE FIELD:", getattr(self.user, "role", None))

        if getattr(self.user, "role", None) in ["admin", "super_admin"]:
            print("ADMIN ACCESS GRANTED")
            return True

        if self.user.role == "driver":
            return Shipment.objects.filter(
                id=self.shipment_id,
                driver__user=self.user
            ).exists()

        if self.user.role == "customer":
            return Shipment.objects.filter(
                id=self.shipment_id,
                customer=self.user
            ).exists()

        print("ACCESS DENIED")
        return False