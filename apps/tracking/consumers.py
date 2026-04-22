import json
import traceback
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

            self.group_name = f"shipment_{self.shipment_id}_{self.role}"

            if not await self.is_authorized():
                await self.close(code=4003)
                return

            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            print(f"CONNECTED: {self.user.id}, ROLE: {self.role}, GROUP: {self.group_name}")

            await self.send_existing_offer()

        except Exception as e:
            print("CONNECT ERROR:", e)
            traceback.print_exc()
            await self.close()

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            if self.role != "driver":
                return

            lat = data.get("lat")
            lng = data.get("lng")

            if lat is None or lng is None:
                return

            is_valid = await self.is_valid_driver_for_shipment()
            if not is_valid:
                return

            lat = float(lat)
            lng = float(lng)

            heading = data.get("heading")
            speed = data.get("speed")

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

            await self.channel_layer.group_send(
                f"shipment_{self.shipment_id}_customer",
                {"type": "location_event", "payload": payload}
            )

            await self.channel_layer.group_send(
                f"shipment_{self.shipment_id}_admin",
                {"type": "location_event", "payload": payload}
            )

        except Exception as e:
            print("RECEIVE ERROR:", e)
            traceback.print_exc()

    # EVENTS
    async def location_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    async def driver_found_event(self, event):
        print("DRIVER FOUND EVENT:", event)
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
                Shipment.objects.filter(id=self.shipment_id, driver__user=self.user).exists()
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
            Shipment.objects.filter(id=self.shipment_id, driver__user=self.user).exists()
            or
            DriverOffer.objects.filter(
                shipment_id=self.shipment_id,
                driver__user=self.user,
                status="pending"
            ).exists()
        )

    @sync_to_async
    def get_driver_status(self):
        shipment = Shipment.objects.filter(
            id=self.shipment_id
        ).select_related("driver__user").first()

        if shipment and shipment.driver and shipment.driver.user_id == self.user.id:
            return "assigned"

        if DriverOffer.objects.filter(
            shipment_id=self.shipment_id,
            driver__user=self.user,
            status="pending"
        ).exists():
            return "temporary"

        return "unknown"

    @sync_to_async
    def get_existing_offer(self):
        return DriverOffer.objects.filter(
            shipment_id=self.shipment_id,
            status="pending"
        ).select_related("driver", "driver__user", "vehicle").first()

    async def send_existing_offer(self):
        offer = await self.get_existing_offer()

        if not offer:
            return

        location = await sync_to_async(
            lambda: DriverLocation.objects.filter(driver=offer.driver).first()
        )()

        lat, lng = None, None
        if location and location.location:
            lat = location.location.y
            lng = location.location.x

        await self.send(text_data=json.dumps({
            "event": "driver_found",
            "data": {
                "driver": {
                    "id": offer.driver.id,
                    "name": offer.driver.user.get_full_name(),
                },
                "vehicle": {
                    "id": offer.vehicle.id,
                },
                "location": {
                    "lat": lat,
                    "lng": lng
                },
                "shipment_id": self.shipment_id,
                "status": "temporary"
            }
        }))