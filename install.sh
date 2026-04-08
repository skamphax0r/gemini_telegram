#!/bin/bash

# Gemini Telegram Bot Installation Script
set -e

echo "--- Gemini Telegram Bot Installer ---"

# 1. Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

if ! python3 -c "import requests" &> /dev/null; then
    echo "Installing 'requests' library..."
    pip3 install requests --quiet
fi

# 2. Get Bot Token
echo "To get a token, message @BotFather on Telegram and use /newbot."
read -p "Enter your Telegram Bot Token: " BOT_TOKEN
if [ -z "$BOT_TOKEN" ]; then
    echo "Error: Token cannot be empty."
    exit 1
fi

# 3. Get User ID by polling
echo ""
echo "Now, go to your bot in Telegram (click the link from @BotFather) and send it a message (e.g., 'hello')."
echo "This allows the installer to identify your User ID and restrict access to ONLY you."
echo "Waiting for message..."

USER_ID=$(python3 -c "
import requests
import time
import sys

token = '$BOT_TOKEN'
url = f'https://api.telegram.org/bot{token}/getUpdates'

while True:
    try:
        r = requests.get(url, params={'timeout': 10}).json()
        if r.get('ok') and r.get('result'):
            # Get the last message's user ID
            print(r['result'][-1]['message']['from']['id'])
            break
    except Exception:
        pass
    time.sleep(2)
")

echo "Detected User ID: $USER_ID"

# 4. Create .env file
echo "Creating .env file..."
cat << EOF > .env
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
ALLOWED_USER_ID=$USER_ID
MAX_THREADS=3
EOF

# 5. Setup Systemd Service
SERVICE_FILE="gemini-telegram-bot.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_SERVICE_DIR"

WORKING_DIR=$(pwd)
PYTHON_PATH=$(which python3)

echo "Generating systemd service file..."
cat << EOF > "$USER_SERVICE_DIR/$SERVICE_FILE"
[Unit]
Description=Gemini CLI Telegram Bot
After=network.target

[Service]
ExecStart=$PYTHON_PATH $WORKING_DIR/telegram_bot.py
WorkingDirectory=$WORKING_DIR
Restart=always
EnvironmentFile=$WORKING_DIR/.env

[Install]
WantedBy=default.target
EOF

# 6. Enable and Start Service
echo "Enabling and starting service..."
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_FILE"
systemctl --user restart "$SERVICE_FILE"

echo "--- Installation Complete! ---"
echo "The bot is now running as a background service."
echo "You can check status with: systemctl --user status $SERVICE_FILE"
echo "You can view logs with: journalctl --user -u $SERVICE_FILE -f"
