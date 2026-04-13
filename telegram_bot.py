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
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
MAX_THREADS = int(os.getenv("MAX_THREADS", "5")) # Increased default for async handling
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
    status: str = "pending"  # pending, parsing, running, completed, failed
    worker_id: int = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = None
    response: str = None
    is_command: bool = False
    is_parsing: bool = False

# Global Queues
update_queue = Queue()
task_queue = Queue()

# Global State
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
    if not text:
        return
    if len(text) > 4000:
        text = text[:3997] + "..."
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(f"{URL}/sendMessage", data=data)
    except Exception as e:
        print(f"Error sending message: {e}")

def call_gemini(prompt, user_id=None, is_parsing=False):
    try:
        session_id = None
        if user_id and not is_parsing:
            with session_lock:
                session_id = user_sessions.get(str(user_id))

        cmd = [
            "gemini",
            "-p", prompt,
            "--approval-mode", "yolo",
            "--output-format", "json"
        ]
        
        if session_id and not is_parsing:
            cmd.extend(["--resume", session_id])

        result = subprocess.run(cmd, capture_output=True, text=True)
        
        output = result.stdout
        start_idx = output.find('{')
        if start_idx != -1:
            json_str = output[start_idx:]
            data = json.loads(json_str)
            
            if user_id and not is_parsing and not session_id:
                list_cmd = ["gemini", "--list-sessions"]
                list_result = subprocess.run(list_cmd, capture_output=True, text=True)
                lines = list_result.stdout.strip().split('\n')
                if lines:
                    last_line = lines[-1]
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

def parse_intent(prompt):
    system_prompt = """
Analyze the user's message and determine if they want to schedule a task or run a command in the future.
Respond ONLY with a JSON object in this format:
{
  "is_scheduled": boolean,
  "delay_seconds": number,
  "is_command": boolean,
  "extracted_task": "string",
  "confirmation_response": "string"
}
"""
    combined_prompt = f"{system_prompt}\nUser Message: {prompt}"
    response = call_gemini(combined_prompt, is_parsing=True)
    try:
        return json.loads(response)
    except:
        return {"is_scheduled": False}

def worker_thread(worker_id):
    global worker_count
    while True:
        try:
            task = task_queue.get(timeout=10)
            with task_lock:
                task.status = "running"
                task.worker_id = worker_id
                task.start_time = datetime.now()
            
            print(f"Worker {worker_id} executing task: {task.prompt[:30]}...")
            
            if task.is_command:
                try:
                    res = subprocess.run(task.prompt, shell=True, capture_output=True, text=True)
                    response = f"Output of '{task.prompt}':\n{res.stdout}\n{res.stderr}"
                except Exception as e:
                    response = f"Error running command: {str(e)}"
            else:
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

def schedule_task(chat_id, user_id, delay_seconds, prompt, is_command=False, confirmation_msg=None):
    if confirmation_msg:
        send_message(chat_id, confirmation_msg)
    
    def delayed_execution():
        new_task = Task(chat_id=chat_id, user_id=user_id, prompt=prompt, is_command=is_command)
        task_queue.put(new_task)
        ensure_workers()

    threading.Timer(delay_seconds, delayed_execution).start()

def ensure_workers():
    global worker_count
    with worker_lock:
        if worker_count < MAX_THREADS:
            worker_count += 1
            t = threading.Thread(target=worker_thread, args=(worker_count,))
            t.daemon = True
            t.start()

def update_processor():
    """Background thread to process incoming Telegram messages without blocking the main loop."""
    while True:
        update = update_queue.get()
        message = update.get("message")
        if not message or "text" not in message:
            update_queue.task_done()
            continue
            
        chat_id = message["chat"]["id"]
        user_id = str(message["from"]["id"])
        prompt = message["text"].strip()

        if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
            send_message(chat_id, "Unauthorized.")
            update_queue.task_done()
            continue

        if prompt == "/status":
            with task_lock:
                status_msg = f"Status on {HOSTNAME}:\n"
                status_msg += f"Workers: {worker_count}/{MAX_THREADS} active\n"
                status_msg += f"Session: {user_sessions.get(user_id, 'None')}\n"
                send_message(chat_id, status_msg)
            update_queue.task_done()
            continue

        if prompt == "/clear":
            with session_lock:
                if user_id in user_sessions:
                    del user_sessions[user_id]
                    save_sessions()
                    send_message(chat_id, "Session cleared.")
                else:
                    send_message(chat_id, "No active session.")
            update_queue.task_done()
            continue

        if prompt == "/start":
            send_message(chat_id, f"Gemini CLI on {HOSTNAME} ready.")
            update_queue.task_done()
            continue

        # Intent parsing (Gemini call) happens here in the background thread
        intent = parse_intent(prompt)
        if intent.get("is_scheduled"):
            schedule_task(
                chat_id, user_id, 
                intent["delay_seconds"], 
                intent["extracted_task"], 
                is_command=intent.get("is_command", False),
                confirmation_msg=intent.get("confirmation_response")
            )
        else:
            new_task = Task(chat_id=chat_id, user_id=user_id, prompt=prompt)
            task_queue.put(new_task)
            ensure_workers()
        
        update_queue.task_done()

def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    try:
        r = requests.get(f"{URL}/getUpdates", params=params)
        return r.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return None

def main():
    load_sessions()
    print(f"Gemini Telegram Bot running on {HOSTNAME} (Max Threads: {MAX_THREADS})")
    
    # Start update processor
    t_proc = threading.Thread(target=update_processor)
    t_proc.daemon = True
    t_proc.start()

    offset = None
    while True:
        updates = get_updates(offset)
        if updates and updates.get("ok"):
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                update_queue.put(update) # Main loop is now truly non-blocking
        time.sleep(1)

if __name__ == "__main__":
    main()
