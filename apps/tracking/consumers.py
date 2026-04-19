import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.shipments.models import Shipment

class DriverLocationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}"

        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        self.shipment_group = None
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group, self.channel_name)

        if self.shipment_group:
            await self.channel_layer.group_discard(
                self.shipment_group,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get("type") == "join_shipment":
            shipment_id = data.get("shipment_id")

            shipment = await database_sync_to_async(Shipment.objects.get)(id=shipment_id)

            # SECURITY CHECK
            if (
                shipment.customer_id != self.user.id and
                (not shipment.driver or shipment.driver.user_id != self.user.id)
            ):
                await self.close()
                return

            self.shipment_group = f"shipment_{shipment_id}"

            await self.channel_layer.group_add(
                self.shipment_group,
                self.channel_name
            )

    async def driver_location(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def shipment_matched(self, event):
        await self.send(text_data=json.dumps(event["data"]))