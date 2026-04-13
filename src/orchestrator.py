from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
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
            # For unauthorized messages, we ignore
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

        # Basic commands
        if content == "/status":
            self.send_response(chat_id, "System ready.")
        elif content == "/start":
            self.send_response(chat_id, "Gemini Orchestrator initialized.")
        elif content == "/clear":
            with self.db._get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE chat_jid = ?", (chat_id,))
            self.send_response(chat_id, "Session cleared.")
        elif content.startswith("/memory"):
            self.handle_memory_command(chat_id, content)
        elif content.startswith("/schedule"):
            self.handle_schedule_command(chat_id, content)
        else:
            self.execute_prompt(chat_id, content)

    def handle_schedule_command(self, chat_id: str, content: str):
        """Handle /schedule <minutes> <prompt>"""
        parts = content.split(" ", 2)
        if len(parts) < 3:
            self.send_response(chat_id, "Usage: /schedule <minutes> <prompt>")
            return
        
        try:
            minutes = int(parts[1])
            prompt = parts[2]
            run_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
            
            self.db.add_task(chat_id, prompt, "once", run_at)
            self.send_response(chat_id, f"Task scheduled to run in {minutes} minutes.")
        except ValueError:
            self.send_response(chat_id, "Invalid number of minutes.")

    def execute_prompt(self, chat_id: str, prompt: str):
        """Invoke Gemini Agent in container and handle response."""
        # Set typing indicator
        channel = self.find_channel_for_chat(chat_id)
        if channel:
            channel.set_typing(chat_id, True)

        # Get session ID for context persistence
        session_id = self.db.get_session(chat_id)
        env_vars = {
            "GEMINI_SESSION_ID": session_id if session_id else ""
        }
        
        result = self.runner.run_agent(chat_id, prompt, env_vars)
        
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
            
            # Update session ID if one was returned
            new_session_id = result.get("session_id")
            if new_session_id:
                self.db.set_session(chat_id, new_session_id)
        else:
            self.send_response(chat_id, f"Error: {result.get('error', 'Unknown agent error')}")

        if channel:
            channel.set_typing(chat_id, False)

    def handle_memory_command(self, chat_id: str, content: str):
        workspace_path = self.runner._get_workspace_path(chat_id)
        gemini_md_path = os.path.join(workspace_path, "GEMINI.md")
        
        parts = content.split(" ", 1)
        if len(parts) == 1:
            # Read memory
            if os.path.exists(gemini_md_path):
                with open(gemini_md_path, "r") as f:
                    memory = f.read()
                    self.send_response(chat_id, f"Current Memory (GEMINI.md):\n\n{memory}")
            else:
                self.send_response(chat_id, "No memory file found.")
        else:
            # Write/Update memory
            new_content = parts[1]
            with open(gemini_md_path, "w") as f:
                f.write(new_content)
            self.send_response(chat_id, "Memory updated successfully.")

    def send_response(self, chat_id: str, text: str):
        channel = self.find_channel_for_chat(chat_id)
        if channel:
            channel.send_message(chat_id, text)

    def find_channel_for_chat(self, chat_id: str) -> Optional[BaseChannel]:
        return self.channels[0] if self.channels else None

    def start(self):
        for channel in self.channels:
            channel.connect()

    def stop(self):
        for channel in self.channels:
            channel.disconnect()
