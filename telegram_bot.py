import subprocess
import json
import time
import requests
import os
import sys
import socket
import threading
from queue import Queue
from dataclasses import dataclass
from datetime import datetime

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
MAX_THREADS = int(os.getenv("MAX_THREADS", "3"))

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

def send_message(chat_id, text):
    # Telegram has a 4096 character limit per message
    if len(text) > 4000:
        text = text[:3997] + "..."
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(f"{URL}/sendMessage", data=data)
    except Exception as e:
        print(f"Error sending message: {e}")

def call_gemini(prompt):
    try:
        # NOTE: Running multiple Gemini instances in the same directory 
        # with --approval-mode yolo can cause file system race conditions.
        cmd = [
            "gemini",
            "-p", prompt,
            "--resume", "latest",
            "--approval-mode", "yolo",
            "--output-format", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        output = result.stdout
        start_idx = output.find('{')
        if start_idx != -1:
            json_str = output[start_idx:]
            data = json.loads(json_str)
            return data.get("response", "No response found in JSON.")
        else:
            return f"Error: Could not parse Gemini output.\nStdout: {output}\nStderr: {result.stderr}"
    except Exception as e:
        return f"Exception while calling Gemini: {str(e)}"

def worker_thread(worker_id):
    global worker_count
    while True:
        try:
            # Get a task from the queue
            task = task_queue.get(timeout=5) # Wait 5 seconds for a task
            
            with task_lock:
                task.status = "running"
                task.worker_id = worker_id
                task.start_time = datetime.now()
            
            print(f"Worker {worker_id} started task: {task.prompt}")
            response = call_gemini(task.prompt)
            
            with task_lock:
                task.status = "completed"
                task.end_time = datetime.now()
                task.response = response
            
            send_message(task.chat_id, response)
            task_queue.task_done()
            
        except:
            # No task found within timeout, terminate worker
            break

    with worker_lock:
        worker_count -= 1
    print(f"Worker {worker_id} terminated (idle).")

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
                prompt = message["text"]

                print(f"Received message from user ID: {user_id}")

                if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
                    print(f"Unauthorized access attempt from user ID: {user_id}")
                    send_message(chat_id, "Unauthorized.")
                    continue

                if prompt == "/status":
                    with task_lock:
                        running = [t for t in active_tasks if t.status == "running"]
                        pending = [t for t in active_tasks if t.status == "pending"]
                        
                        status_msg = f"Status on {HOSTNAME}:\n"
                        status_msg += f"Workers: {worker_count}/{MAX_THREADS} active\n\n"
                        
                        if running:
                            status_msg += "🚀 Running Tasks:\n"
                            for t in running:
                                status_msg += f"- {t.prompt[:30]}... (Worker {t.worker_id})\n"
                        
                        if pending:
                            status_msg += "\n⏳ Queued Tasks:\n"
                            for t in pending:
                                status_msg += f"- {t.prompt[:30]}...\n"
                                
                        if not running and not pending:
                            status_msg += "Currently idle."
                            
                        send_message(chat_id, status_msg)
                    continue

                if prompt == "/start":
                    send_message(chat_id, f"Gemini CLI on {HOSTNAME} ready. Max threads: {MAX_THREADS}")
                    continue

                # New Task Logic
                with worker_lock:
                    with task_lock:
                        # Clean up old completed tasks from the active_tasks list
                        active_tasks[:] = [t for t in active_tasks if t.status in ["pending", "running"]]
                        
                        if len(active_tasks) >= MAX_THREADS + 5: # Basic buffer
                            send_message(chat_id, "System busy. Please wait for current tasks to complete.")
                            continue

                        new_task = Task(chat_id=chat_id, user_id=user_id, prompt=prompt)
                        active_tasks.append(new_task)
                        task_queue.put(new_task)

                        if worker_count < MAX_THREADS:
                            worker_count += 1
                            t = threading.Thread(target=worker_thread, args=(worker_count,))
                            t.daemon = True
                            t.start()
                        else:
                            send_message(chat_id, f"All {MAX_THREADS} workers busy. Task queued.")

        time.sleep(1)

if __name__ == "__main__":
    main()
