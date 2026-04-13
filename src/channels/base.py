from abc import ABC, abstractmethod
from typing import Callable, Optional

class BaseChannel(ABC):
    @abstractmethod
    def connect(self):
        """Establish connection with the messaging platform."""
        pass

    @abstractmethod
    def disconnect(self):
        """Close connection with the messaging platform."""
        pass

    @abstractmethod
    def send_message(self, chat_id: str, text: str):
        """Send a message to a specific chat."""
        pass

    @abstractmethod
    def set_typing(self, chat_id: str, is_typing: bool):
        """Set or unset the typing indicator."""
        pass

    def set_on_message(self, callback: Callable[[str, str, dict], None]):
        """Set callback for incoming messages (chat_id, sender, raw_msg)."""
        self.on_message = callback
