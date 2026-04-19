import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.shipments.models import Shipment

class DriverLocationConsumer(AsyncWebsocketConsumer):

    ''' async def connect(self):
        self.user = self.scope.get("user")

        if self.user.is_anonymous:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}"
        self.shipment_group = None

        await self.accept()

        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        ) '''

    async def connect(self):
        self.user = self.scope.get("user")

        # DEBUG MODE ONLY
        self.user_group = None
        self.shipment_group = None

        await self.accept()

    async def disconnect(self, close_code):
        # SAFE GUARDS
        if getattr(self, "user_group", None):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )

        if getattr(self, "shipment_group", None):
            await self.channel_layer.group_discard(
                self.shipment_group,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get("type") == "join_shipment":
            shipment_id = data.get("shipment_id")

            self.shipment_group = f"shipment_{shipment_id}"

            await self.channel_layer.group_add(
                self.shipment_group,
                self.channel_name
            )

    async def driver_location(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def shipment_matched(self, event):
        await self.send(text_data=json.dumps(event["data"]))