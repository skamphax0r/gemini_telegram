from typing import List, Optional, Dict, Any
from datetime import datetime
from .database import Database
from .channels.base import BaseChannel
from .runner import ContainerRunner
import os

class Orchestrator:
    def __init__(self, db: Database, channels: List[BaseChannel], runner: ContainerRunner, allowed_user_id: Optional[str] = None):
        self.db = db
        self.channels = channels
        self.runner = runner
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
            # Set typing indicator
            channel = self.find_channel_for_chat(chat_id)
            if channel:
                channel.set_typing(chat_id, True)

            # Invoke Gemini Agent in container
            env_vars = {
                "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", "dummy_key")
            }
            
            result = self.runner.run_agent(chat_id, content, env_vars)
            
            if result.get("status") == "success":
                response_text = result.get("response", "No response.")
                self.send_response(chat_id, response_text)
                
                # Store bot response in DB
                self.db.store_message(
                    chat_jid=chat_id,
                    sender="bot",
                    content=response_text,
                    timestamp=datetime.now().isoformat(),
                    is_from_me=True,
                    is_bot_message=True
                )
            else:
                self.send_response(chat_id, f"Error: {result.get('error', 'Unknown agent error')}")

            if channel:
                channel.set_typing(chat_id, False)

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
