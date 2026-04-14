#!/bin/bash

# Gemini Telegram Bot Installation Script
set -e

echo "--- Gemini Telegram Bot Installer ---"

# 1. Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

if ! command -v docker &> /dev/null && ! command -v podman &> /dev/null; then
    echo "Error: Neither docker nor podman found. One is required for container isolation."
    exit 1
fi

# 2. Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install requests python-dotenv

# 3. Build Agent Container Image
echo "Building Gemini Agent container image..."
# Use sudo for build if needed (assuming user has permissions)
BUILD_CMD="docker"
if command -v podman &> /dev/null; then
    BUILD_CMD="podman"
fi

sudo $BUILD_CMD build -t gemini-agent:latest ./src/agent

# 4. Setup Service
echo "Setting up systemd service..."
SERVICE_FILE="gemini-telegram-bot.service"
WORKING_DIR=$(pwd)
PYTHON_PATH=$(which python3)

sudo tee /etc/systemd/system/$SERVICE_FILE <<EOF
[Unit]
Description=Gemini CLI Telegram Bot
After=network.target

[Service]
ExecStart=$PYTHON_PATH -u $WORKING_DIR/telegram_bot.py
WorkingDirectory=$WORKING_DIR
Restart=always
User=$(whoami)
# Note: Load environment variables from .env if present
# Or add them manually here
EnvironmentFile=$WORKING_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_FILE

echo "--- Installation Complete! ---"
echo "1. Please ensure your .env file has TELEGRAM_BOT_TOKEN and ALLOWED_USER_ID."
echo "2. Start the service with: sudo systemctl start $SERVICE_FILE"
echo "3. View logs with: journalctl -u $SERVICE_FILE -f"
