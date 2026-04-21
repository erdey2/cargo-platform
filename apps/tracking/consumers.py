import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.gis.geos import Point
from django.core.exceptions import ObjectDoesNotExist

from apps.tracking.models import DriverLocation
from apps.drivers.models import DriverProfile
from apps.shipments.models import Shipment
from apps.matching.models import DriverOffer


class DriverLocationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return

        try:
            self.shipment_id = self.scope["url_route"]["kwargs"]["shipment_id"]
            self.role = await self.get_role()

            # group per role
            self.group_name = f"shipment_{self.shipment_id}_{self.role}"

            if not await self.is_authorized():
                await self.close(code=4003)
                return

            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

        except Exception as e:
            print("CONNECT ERROR:", e)
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            lat = data.get("lat")
            lng = data.get("lng")

            if lat is None or lng is None:
                return

            # ONLY DRIVER CAN SEND
            if self.role != "driver":
                return

            # VALIDATE driver belongs to shipment (important!)
            is_valid = await self.is_valid_driver_for_shipment()
            if not is_valid:
                return

            lat = float(lat)
            lng = float(lng)

            heading = data.get("heading")
            speed = data.get("speed")

            # Save location
            await self.save_location(lat, lng, heading, speed)

            status = await self.get_driver_status()

            payload = {
                "event": "driver.location",
                "data": {
                    "driver_id": self.user.id,
                    "shipment_id": self.shipment_id,
                    "lat": lat,
                    "lng": lng,
                    "heading": heading,
                    "speed": speed,
                    "status": status,
                }
            }

            # Send to customer
            await self.channel_layer.group_send(
                f"shipment_{self.shipment_id}_customer",
                {"type": "location_event", "payload": payload}
            )

            # Send to admin
            await self.channel_layer.group_send(
                f"shipment_{self.shipment_id}_admin",
                {"type": "location_event", "payload": payload}
            )

        except Exception as e:
            print("RECEIVE ERROR:", e)

    # EVENT HANDLERS

    async def location_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    async def driver_found_event(self, event):
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
            pass

    @sync_to_async
    def is_authorized(self):

        if self.user.role in ["admin", "super_admin"]:
            return True

        if self.user.role == "driver":
            return (
                Shipment.objects.filter(
                    id=self.shipment_id,
                    driver__user=self.user
                ).exists()
                or
                DriverOffer.objects.filter(
                    shipment_id=self.shipment_id,
                    driver__user=self.user,
                    status="pending"
                ).exists()
            )

        if self.user.role == "customer":
            return Shipment.objects.filter(
                id=self.shipment_id,
                customer=self.user
            ).exists()

        return False

    @sync_to_async
    def is_valid_driver_for_shipment(self):
        return (
            Shipment.objects.filter(
                id=self.shipment_id,
                driver__user=self.user
            ).exists()
            or
            DriverOffer.objects.filter(
                shipment_id=self.shipment_id,
                driver__user=self.user,
                status="pending"
            ).exists()
        )

    @sync_to_async
    def get_driver_status(self):

        if Shipment.objects.filter(
            id=self.shipment_id,
            driver__user=self.user
        ).exists():
            return "assigned"

        if DriverOffer.objects.filter(
            shipment_id=self.shipment_id,
            driver__user=self.user,
            status="pending"
        ).exists():
            return "temporary"

        return "unknown"