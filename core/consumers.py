import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Room, Participant

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            print("WebSocket connect method called")
            self.room_code = self.scope['url_route']['kwargs']['room_code']
            self.room_group_name = f'room_{self.room_code}'

            # Join room group
            # await self.channel_layer.group_add(
            #     self.room_group_name,
            #     self.channel_name
            # )

            await self.accept()
            print(f"WebSocket connected to room: {self.room_code}")
        except Exception as e:
            print(f"Error in WebSocket connect: {e}")
            await self.close()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        # For now, we don't need to receive messages from the client
        pass

    # Receive message from room group
    async def participant_update(self, event):
        participants = event['participants']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'participant_update',
            'participants': participants
        }))
    
    async def send_participant_list(self):
        room = await self.get_room()
        if room:
            participants = await self.get_participants(room)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_update',
                    'participants': participants
                }
            )

    @database_sync_to_async
    def get_room(self):
        try:
            return Room.objects.get(code=self.room_code)
        except Room.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_participants(self, room):
        return list(room.participants.values_list('name', flat=True))
