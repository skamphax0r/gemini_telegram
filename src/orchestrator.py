from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import os
import sys
import subprocess
import threading
import time
import concurrent.futures
from .database import Database
from .channels.base import BaseChannel
from .runner import ContainerRunner

class Orchestrator:
    def __init__(self, db: Database, channels: List[BaseChannel], runner: ContainerRunner, allowed_user_id: Optional[str] = None):
        self.db = db
        self.channels = channels
        self.runner = runner
        self.allowed_user_id = allowed_user_id
        self.start_time = datetime.now()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        self._locks_mutex = threading.Lock()
        self._chat_locks: Dict[str, threading.Lock] = {}
        
        for channel in self.channels:
            channel.set_on_message(self.handle_message)

    def _get_chat_lock(self, chat_id: str) -> threading.Lock:
        with self._locks_mutex:
            if chat_id not in self._chat_locks:
                self._chat_locks[chat_id] = threading.Lock()
            return self._chat_locks[chat_id]

    def handle_message(self, chat_id: str, sender: str, raw_msg: dict):
        # Security check
        if self.allowed_user_id and sender != self.allowed_user_id:
            return

        # Handle messages in a separate thread to avoid blocking the channel's poll loop
        self.executor.submit(self._process_message_thread, chat_id, sender, raw_msg)

    def _process_message_thread(self, chat_id: str, sender: str, raw_msg: dict):
        content = raw_msg.get("text", "").strip()
        timestamp = datetime.now().isoformat()
        
        # Store message in DB
        try:
            self.db.store_message(
                chat_jid=chat_id,
                sender=sender,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                is_bot_message=False,
                metadata=raw_msg
            )
        except Exception as e:
            print(f"Error storing message in DB: {e}")

        # Basic commands
        if content == "/status":
            self.handle_status_command(chat_id)
        elif content == "/start":
            self.send_response(chat_id, "AGY Orchestrator initialized.")
        elif content == "/clear":
            try:
                with self.db._get_connection() as conn:
                    conn.execute("DELETE FROM sessions WHERE chat_jid = ?", (chat_id,))
                self.send_response(chat_id, "Session cleared.")
            except Exception as e:
                self.send_response(chat_id, f"Error clearing session: {e}")
        elif content.startswith("/memory"):
            self.handle_memory_command(chat_id, content)
        elif content.startswith("/schedule"):
            self.handle_schedule_command(chat_id, content)
        elif content.startswith("/subagent") or content.startswith("/delegate"):
            self.handle_subagent_command(chat_id, content)
        else:
            self.execute_prompt(chat_id, content)

    def handle_status_command(self, chat_id: str):
        uptime = datetime.now() - self.start_time
        # Format uptime string
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        python_ver = sys.version.split()[0]
        
        # Get AGY version from host
        try:
            home_dir = os.path.expanduser("~")
            agy_candidates = [
                shutil.which("agy"),
                os.path.join(home_dir, ".local", "bin", "agy"),
                "/usr/local/bin/agy",
                "/usr/bin/agy",
                shutil.which("gemini"),
                os.path.join(home_dir, ".local", "bin", "gemini")
            ]
            agy_bin = next((p for p in agy_candidates if p and os.path.isfile(p) and os.access(p, os.X_OK)), "agy")
            agy_ver = subprocess.check_output([agy_bin, "--version"], text=True, stderr=subprocess.STDOUT).strip()
        except:
            agy_ver = "Unknown"

        status_msg = (
            "🤖 *AGY Bot Status*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ *System*: Ready\n"
            f"🕒 *Uptime*: `{uptime_str}`\n"
            f"🐍 *Python*: `{python_ver}`\n"
            f"⚡ *AGY CLI*: `{agy_ver}`\n"
            f"📦 *Runtime*: `{self.runner.runtime}`\n"
            f"👤 *User ID*: `{self.allowed_user_id or 'Any'}`"
        )
        self.send_response(chat_id, status_msg)

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

    def handle_subagent_command(self, chat_id: str, content: str):
        """Handle /subagent <prompt> or /delegate <prompt>"""
        parts = content.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            self.send_response(chat_id, "Usage: /subagent <prompt>")
            return
        task_prompt = parts[1].strip()
        self.send_response(
            chat_id,
            "🚀 Delegated to a background subagent (30m timeout). I'll send the results here as soon as it finishes."
        )
        self.executor.submit(self.execute_subagent_prompt, chat_id, task_prompt)

    def _drain_subagent_queue(self, chat_id: str):
        """Check if the main agent queued any detached background subagent tasks during its run."""
        try:
            workspace_path = self.runner._get_workspace_path(chat_id)
            if not isinstance(workspace_path, str) or not os.path.isdir(workspace_path):
                return
            queue_file = os.path.join(workspace_path, ".subagent_tasks.jsonl")
            if not os.path.isfile(queue_file):
                return
            with open(queue_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            os.remove(queue_file)
            for line in lines:
                try:
                    data = json.loads(line)
                    task_prompt = data.get("prompt", "").strip()
                    if task_prompt:
                        self.executor.submit(self.execute_subagent_prompt, chat_id, task_prompt)
                except Exception as e:
                    print(f"Error parsing queued subagent task: {e}")
        except Exception as e:
            print(f"Error draining subagent queue: {e}")

    def execute_subagent_prompt(self, chat_id: str, prompt: str, timeout: int = 1800):
        """Run a delegated prompt in an isolated subagent container/session without blocking the main conversation."""
        try:
            env_vars = {
                "AGY_CONVERSATION_ID": "",
                "AGY_SESSION_ID": "",
                "GEMINI_SESSION_ID": "",
                "AGY_AGENT_TIMEOUT": str(max(60, timeout - 10)),
            }
            result = self.runner.run_agent(chat_id, prompt, env_vars, timeout=timeout)
            if result.get("status") == "success":
                response_text = result.get("response", "Subagent completed with no output.")
                self.send_response(chat_id, response_text)
                try:
                    self.db.store_message(
                        chat_jid=chat_id,
                        sender="bot",
                        content=response_text,
                        timestamp=datetime.now().isoformat(),
                        is_from_me=True,
                        is_bot_message=True
                    )
                except Exception as e:
                    print(f"Error storing subagent response in DB: {e}")
            else:
                self.send_response(chat_id, f"Subagent Error: {result.get('error', 'Unknown subagent error')}")
        except Exception as e:
            self.send_response(chat_id, f"Subagent Error: {e}")

    def execute_prompt(self, chat_id: str, prompt: str):
        """Invoke AGY Agent in container and handle response."""
        channel = self.find_channel_for_chat(chat_id)
        chat_lock = self._get_chat_lock(chat_id)
        
        # Start a background thread to keep the typing indicator active
        typing_active = True
        def typing_loop():
            while typing_active:
                if channel:
                    channel.set_typing(chat_id, True)
                time.sleep(4)

        typing_thread = threading.Thread(target=typing_loop)
        typing_thread.daemon = True
        typing_thread.start()

        try:
            with chat_lock:
                # Get session ID for context persistence
                session_id = self.db.get_session(chat_id)
                env_vars = {
                    "AGY_CONVERSATION_ID": session_id if session_id else "",
                    "AGY_SESSION_ID": session_id if session_id else "",
                    "GEMINI_SESSION_ID": session_id if session_id else ""
                }
                
                result = self.runner.run_agent(chat_id, prompt, env_vars)
                
                if result.get("status") == "success":
                    response_text = result.get("response", "No response.")
                    self.send_response(chat_id, response_text)
                    
                    # Store bot response in DB
                    try:
                        self.db.store_message(
                            chat_jid=chat_id,
                            sender="bot",
                            content=response_text,
                            timestamp=datetime.now().isoformat(),
                            is_from_me=True,
                            is_bot_message=True
                        )
                    except Exception as e:
                        print(f"Error storing bot response in DB: {e}")
                    
                    # Update session ID if one was returned
                    new_session_id = result.get("session_id")
                    if new_session_id:
                        try:
                            self.db.set_session(chat_id, new_session_id)
                        except Exception as e:
                            print(f"Error updating session in DB: {e}")
                else:
                    self.send_response(chat_id, f"Error: {result.get('error', 'Unknown agent error')}")
                
                # Drain any detached subagent tasks queued during this run
                self._drain_subagent_queue(chat_id)
        finally:
            typing_active = False
            if channel:
                channel.set_typing(chat_id, False)

    def handle_memory_command(self, chat_id: str, content: str):
        workspace_path = self.runner._get_workspace_path(chat_id)
        agy_md_path = os.path.join(workspace_path, "AGY.md")
        gemini_md_path = os.path.join(workspace_path, "GEMINI.md")
        
        target_path = agy_md_path if os.path.exists(agy_md_path) else (gemini_md_path if os.path.exists(gemini_md_path) else agy_md_path)
        
        parts = content.split(" ", 1)
        if len(parts) == 1:
            # Read memory
            if os.path.exists(target_path):
                with open(target_path, "r") as f:
                    memory = f.read()
                    filename = os.path.basename(target_path)
                    self.send_response(chat_id, f"Current Memory ({filename}):\n\n{memory}")
            else:
                self.send_response(chat_id, "No memory file found.")
        else:
            # Write/Update memory
            new_content = parts[1]
            with open(agy_md_path, "w") as f:
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
