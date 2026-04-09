import subprocess
import json
import time
import requests
import os
import sys
import socket
import threading
import re
from queue import Queue
from dataclasses import dataclass
from datetime import datetime

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
MAX_THREADS = int(os.getenv("MAX_THREADS", "3"))
SESSION_FILE = "user_sessions.json"

if not TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
    sys.exit(1)

URL = f"https://api.telegram.org/bot{TOKEN}"
HOSTNAME = socket.gethostname()

@dataclass
class Task:
    chat_id: int
    user_id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    worker_id: int = None
    start_time: datetime = None
    end_time: datetime = None
    response: str = None

# Global State
task_queue = Queue()
active_tasks = []
task_lock = threading.Lock()
worker_count = 0
worker_lock = threading.Lock()

# User Sessions State
user_sessions = {}
session_lock = threading.Lock()

def load_sessions():
    global user_sessions
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                user_sessions = json.load(f)
        except Exception as e:
            print(f"Error loading sessions: {e}")

def save_sessions():
    with session_lock:
        try:
            with open(SESSION_FILE, "w") as f:
                json.dump(user_sessions, f)
        except Exception as e:
            print(f"Error saving sessions: {e}")

def send_message(chat_id, text):
    # Telegram has a 4096 character limit per message
    if len(text) > 4000:
        text = text[:3997] + "..."
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(f"{URL}/sendMessage", data=data)
    except Exception as e:
        print(f"Error sending message: {e}")

def call_gemini(prompt, user_id=None):
    try:
        session_id = None
        if user_id:
            with session_lock:
                session_id = user_sessions.get(str(user_id))

        cmd = [
            "gemini",
            "-p", prompt,
            "--approval-mode", "yolo",
            "--output-format", "json"
        ]
        
        if session_id:
            cmd.extend(["--resume", session_id])

        result = subprocess.run(cmd, capture_output=True, text=True)
        
        output = result.stdout
        start_idx = output.find('{')
        if start_idx != -1:
            json_str = output[start_idx:]
            data = json.loads(json_str)
            
            if not session_id:
                list_cmd = ["gemini", "--list-sessions"]
                list_result = subprocess.run(list_cmd, capture_output=True, text=True)
                lines = list_result.stdout.strip().split('\n')
                if lines:
                    last_line = lines[-1]
                    import re
                    match = re.search(r'\[(.*?)\]', last_line)
                    if match:
                        new_uuid = match.group(1)
                        with session_lock:
                            user_sessions[str(user_id)] = new_uuid
                        save_sessions()

            return data.get("response", "No response found in JSON.")
        else:
            return f"Error: Could not parse Gemini output.\nStdout: {output}\nStderr: {result.stderr}"
    except Exception as e:
        return f"Exception while calling Gemini: {str(e)}"

def worker_thread(worker_id):
    global worker_count
    while True:
        try:
            task = task_queue.get(timeout=5)
            
            with task_lock:
                task.status = "running"
                task.worker_id = worker_id
                task.start_time = datetime.now()
            
            print(f"Worker {worker_id} started task: {task.prompt}")
            response = call_gemini(task.prompt, user_id=task.user_id)
            
            with task_lock:
                task.status = "completed"
                task.end_time = datetime.now()
                task.response = response
            
            send_message(task.chat_id, response)
            task_queue.task_done()
            
        except:
            break

    with worker_lock:
        worker_count -= 1

def schedule_reply(chat_id, delay_seconds, message_text="⏰ This is your scheduled reply!"):
    """Sends a message after a delay."""
    def delayed_send():
        send_message(chat_id, message_text)
    
    t = threading.Timer(delay_seconds, delayed_send)
    t.start()
    return t

def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    try:
        r = requests.get(f"{URL}/getUpdates", params=params)
        return r.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return None

def main():
    global worker_count
    load_sessions()
    print(f"Gemini Telegram Bot running on {HOSTNAME} (Max Threads: {MAX_THREADS})")
    
    offset = None
    while True:
        updates = get_updates(offset)
        if updates and updates.get("ok"):
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message or "text" not in message:
                    continue
                    
                chat_id = message["chat"]["id"]
                user_id = str(message["from"]["id"])
                prompt = message["text"].strip()

                if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
                    send_message(chat_id, "Unauthorized.")
                    continue

                # Check for "reply in X min" pattern
                match = re.search(r"reply in (\d+)\s*(min|minute|minutes|hr|hour|hours|sec|second|seconds)", prompt, re.IGNORECASE)
                if match:
                    amount = int(match.group(1))
                    unit = match.group(2).lower()
                    
                    seconds = amount
                    if "min" in unit:
                        seconds = amount * 60
                    elif "hr" in unit or "hour" in unit:
                        seconds = amount * 3600
                    
                    schedule_reply(chat_id, seconds, f"⏰ You asked me to reply in {amount} {unit}. Here I am!")
                    send_message(chat_id, f"OK! I will reply to you in {amount} {unit}.")
                    continue

                if prompt == "/status":
                    with task_lock:
                        status_msg = f"Status on {HOSTNAME}:\n"
                        status_msg += f"Workers: {worker_count}/{MAX_THREADS} active\n"
                        status_msg += f"Session ID: {user_sessions.get(user_id, 'None')}\n"
                        send_message(chat_id, status_msg)
                    continue

                if prompt == "/clear":
                    with session_lock:
                        if user_id in user_sessions:
                            del user_sessions[user_id]
                            save_sessions()
                            send_message(chat_id, "Session cleared.")
                        else:
                            send_message(chat_id, "No active session to clear.")
                    continue

                if prompt == "/start":
                    send_message(chat_id, f"Gemini CLI on {HOSTNAME} ready. Session persistence enabled.")
                    continue

                # New Task Logic
                with worker_lock:
                    with task_lock:
                        active_tasks[:] = [t for t in active_tasks if t.status in ["pending", "running"]]
                        if len(active_tasks) >= MAX_THREADS + 5:
                            send_message(chat_id, "System busy.")
                            continue

                        new_task = Task(chat_id=chat_id, user_id=user_id, prompt=prompt)
                        active_tasks.append(new_task)
                        task_queue.put(new_task)

                        if worker_count < MAX_THREADS:
                            worker_count += 1
                            t = threading.Thread(target=worker_thread, args=(worker_count,))
                            t.daemon = True
                            t.start()
        time.sleep(1)

if __name__ == "__main__":
    main()
