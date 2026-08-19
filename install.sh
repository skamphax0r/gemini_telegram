#!/bin/bash

# AGY Telegram Bot Installation Script
set -e

echo "--- AGY Telegram Bot Installer ---"

# 1. Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

if ! command -v docker &> /dev/null && ! command -v podman &> /dev/null; then
    echo "Error: Neither docker nor podman found. One is required for container isolation."
    exit 1
fi

if ! command -v agy &> /dev/null; then
    echo "Warning: agy CLI not found in PATH. Please ensure Antigravity CLI (agy) is installed."
fi

# 2. Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install requests python-dotenv

# 3. Build Agent Container Image
echo "Building AGY Agent container image..."
# Use sudo for build if needed (assuming user has permissions)
BUILD_CMD="docker"
if command -v podman &> /dev/null; then
    BUILD_CMD="podman"
fi

sudo $BUILD_CMD build -t agy-agent:latest ./src/agent

# 4. Verify AGY CLI Authentication
echo "Checking AGY CLI authentication..."
AGY_BIN=$(command -v agy || echo "$HOME/.local/bin/agy")
if [ -x "$AGY_BIN" ]; then
    if ! "$AGY_BIN" -p "ping" --output-format json &>/dev/null; then
        echo "AGY CLI requires authentication. Starting interactive login..."
        "$AGY_BIN" -p "ping" || true
    else
        echo "AGY CLI authentication verified."
    fi
fi

# 5. Setup Service
echo "Setting up systemd service..."
SERVICE_FILE="agy-telegram-bot.service"
WORKING_DIR=$(pwd)
PYTHON_PATH=$(which python3)

sudo tee /etc/systemd/system/$SERVICE_FILE <<EOF
[Unit]
Description=AGY CLI Telegram Bot
After=network.target

[Service]
Environment=PATH=$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=HOME=$HOME
ExecStart=$PYTHON_PATH -u $WORKING_DIR/telegram_bot.py
WorkingDirectory=$WORKING_DIR
Restart=always
User=$(whoami)
# Note: load_dotenv() in src/main.py will load the .env file automatically
# from the WorkingDirectory.

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_FILE

echo "--- Installation Complete! ---"
echo "1. Please ensure your .env file has TELEGRAM_BOT_TOKEN and ALLOWED_USER_ID."
echo "2. Start the service with: sudo systemctl start $SERVICE_FILE"
echo "3. View logs with: journalctl -u $SERVICE_FILE -f"

