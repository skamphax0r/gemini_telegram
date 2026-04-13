from typing import List, Optional
from datetime import datetime
from .database import Database
from .channels.base import BaseChannel

class Orchestrator:
    def __init__(self, db: Database, channels: List[BaseChannel], allowed_user_id: Optional[str] = None):
        self.db = db
        self.channels = channels
        self.allowed_user_id = allowed_user_id
        
        for channel in self.channels:
            channel.set_on_message(self.handle_message)

    def handle_message(self, chat_id: str, sender: str, raw_msg: dict):
        # Security check
        if self.allowed_user_id and sender != self.allowed_user_id:
            for channel in self.channels:
                if isinstance(channel, type(self.find_channel_for_chat(chat_id))):
                    channel.send_message(chat_id, "Unauthorized.")
            return

        content = raw_msg.get("text", "").strip()
        timestamp = datetime.now().isoformat()
        
        # Store message in DB
        self.db.store_message(
            chat_jid=chat_id,
            sender=sender,
            content=content,
            timestamp=timestamp,
            is_from_me=False,
            is_bot_message=False,
            metadata=raw_msg
        )

        # Initial logic: respond to basic commands
        if content == "/status":
            self.send_response(chat_id, "System ready.")
        elif content == "/start":
            self.send_response(chat_id, "Gemini Orchestrator initialized.")
        elif content == "/clear":
            # Logic for clearing session will be added when session manager is built
            self.send_response(chat_id, "Session clearing not yet implemented in orchestrator.")
        else:
            # Placeholder for Gemini call
            self.send_response(chat_id, f"Received: {content}. (Gemini integration coming in next commits)")

    def send_response(self, chat_id: str, text: str):
        # Find the correct channel (for now, just use the first one if only one exists)
        if self.channels:
            self.channels[0].send_message(chat_id, text)

    def find_channel_for_chat(self, chat_id: str) -> Optional[BaseChannel]:
        # Simple implementation for now
        return self.channels[0] if self.channels else None

    def start(self):
        for channel in self.channels:
            channel.connect()

    def stop(self):
        for channel in self.channels:
            channel.disconnect()
