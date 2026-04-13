import requests
import time
import threading
from typing import Optional, Callable
from .base import BaseChannel

class TelegramChannel(BaseChannel):
    def __init__(self, token: str):
        self.token = token
        self.url = f"https://api.telegram.org/bot{token}"
        self.offset = None
        self.running = False
        self._thread = None
        self.on_message = None

    def connect(self):
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop)
        self._thread.daemon = True
        self._thread.start()

    def disconnect(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def send_message(self, chat_id: str, text: str):
        if not text:
            return
        # Basic chunking for long messages
        if len(text) > 4000:
            text = text[:3997] + "..."
        data = {"chat_id": chat_id, "text": text}
        try:
            requests.post(f"{self.url}/sendMessage", data=data)
        except Exception as e:
            print(f"Error sending message to Telegram: {e}")

    def set_typing(self, chat_id: str, is_typing: bool):
        if not is_typing:
            return # Telegram typing times out automatically
        data = {"chat_id": chat_id, "action": "typing"}
        try:
            requests.post(f"{self.url}/sendChatAction", data=data)
        except Exception as e:
            print(f"Error setting typing on Telegram: {e}")

    def _poll_loop(self):
        while self.running:
            try:
                params = {"timeout": 30, "offset": self.offset}
                r = requests.get(f"{self.url}/getUpdates", params=params)
                updates = r.json()
                if updates.get("ok"):
                    for update in updates.get("result", []):
                        self.offset = update["update_id"] + 1
                        self._process_update(update)
            except Exception as e:
                print(f"Error polling Telegram updates: {e}")
            time.sleep(1)

    def _process_update(self, update):
        if "message" in update and "text" in update["message"]:
            msg = update["message"]
            chat_id = str(msg["chat"]["id"])
            sender = str(msg["from"]["id"])
            if self.on_message:
                self.on_message(chat_id, sender, msg)
