import os
import signal
import sys
import time
from dotenv import load_dotenv

from .database import Database
from .channels.telegram import TelegramChannel
from .orchestrator import Orchestrator
from .runner import ContainerRunner
from .scheduler import TaskScheduler

def main():
    load_dotenv()
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    allowed_user_id = os.environ.get("ALLOWED_USER_ID")
    
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set in environment.")
        sys.exit(1)

    # 1. Initialize Database
    db = Database("gemini_bot.db")
    
    # 2. Initialize Container Runner
    runner = ContainerRunner(
        image_name="gemini-agent:latest",
        runtime="auto",
        base_workspace_dir=os.path.join(os.getcwd(), "workspaces")
    )
    
    # 3. Initialize Telegram Channel
    telegram = TelegramChannel(token)
    
    # 4. Initialize Orchestrator
    orchestrator = Orchestrator(
        db=db, 
        channels=[telegram], 
        runner=runner, 
        allowed_user_id=allowed_user_id
    )
    
    # 5. Initialize Task Scheduler
    scheduler = TaskScheduler(db, orchestrator)

    # Handle termination signals
    def signal_handler(sig, frame):
        print("\nShutting down Gemini Bot...")
        scheduler.stop()
        orchestrator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("--- Gemini Bot Starting ---")
    print(f"Allowed User ID: {allowed_user_id or 'Any'}")
    
    # Start background threads
    scheduler.start()
    orchestrator.start()
    
    print("Bot is now running. Press Ctrl+C to stop.")
    
    # Keep main thread alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
