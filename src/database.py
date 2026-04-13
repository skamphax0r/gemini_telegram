import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

class Database:
    def __init__(self, db_path: str = "gemini_bot.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_jid TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_from_me BOOLEAN NOT NULL,
                    is_bot_message BOOLEAN NOT NULL,
                    metadata TEXT
                )
            """)

            # Sessions table (mapping chat_jid to Gemini UUIDs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    chat_jid TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Tasks table (scheduled events)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_jid TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    script TEXT,
                    schedule_type TEXT NOT NULL, -- 'once', 'recurring'
                    schedule_value TEXT NOT NULL, -- cron expression or ISO timestamp
                    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
                    next_run TEXT,
                    last_run TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Chat metadata (group info, activation status)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_metadata (
                    chat_jid TEXT PRIMARY KEY,
                    name TEXT,
                    is_group BOOLEAN,
                    is_registered BOOLEAN DEFAULT 0,
                    folder_path TEXT,
                    last_activity TEXT,
                    channel TEXT
                )
            """)

            # Router state (persistent cursors)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS router_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            conn.commit()

    # --- Message Methods ---
    def store_message(self, chat_jid: str, sender: str, content: str, timestamp: str, is_from_me: bool, is_bot_message: bool, metadata: Optional[Dict] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (chat_jid, sender, content, timestamp, is_from_me, is_bot_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_jid, sender, content, timestamp, is_from_me, is_bot_message, json.dumps(metadata) if metadata else None))
            conn.commit()

    def get_messages(self, chat_jid: str, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?
            """, (chat_jid, limit))
            return [dict(row) for row in reversed(cursor.fetchall())]

    # --- Session Methods ---
    def set_session(self, chat_jid: str, session_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (chat_jid, session_id, updated_at)
                VALUES (?, ?, ?)
            """, (chat_jid, session_id, now))
            conn.commit()

    def get_session(self, chat_jid: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id FROM sessions WHERE chat_jid = ?", (chat_jid,))
            row = cursor.fetchone()
            return row["session_id"] if row else None

    # --- Task Methods ---
    def add_task(self, chat_jid: str, prompt: str, schedule_type: str, schedule_value: str, script: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO tasks (chat_jid, prompt, schedule_type, schedule_value, script, created_at, next_run)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_jid, prompt, schedule_type, schedule_value, script, now, schedule_value))
            conn.commit()

    def get_pending_tasks(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                SELECT * FROM tasks WHERE status = 'pending' AND next_run <= ?
            """, (now,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Metadata Methods ---
    def register_chat(self, chat_jid: str, name: str, is_group: bool, folder_path: str, channel: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO chat_metadata (chat_jid, name, is_group, is_registered, folder_path, last_activity, channel)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_jid, name, is_group, 1, folder_path, now, channel))
            conn.commit()

    def get_registered_chats(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_metadata WHERE is_registered = 1")
            return [dict(row) for row in cursor.fetchall()]
