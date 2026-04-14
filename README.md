# Gemini Telegram Bot (NanoClaw-Style)

A high-performance, secure, and persistent Telegram bot interface for Gemini AI, inspired by the NanoClaw architecture.

## Key Features

- **Container Isolation**: All Gemini processing and tool execution (shell commands, web searches) run in isolated Docker/Podman containers.
- **Persistent Workspace Memory**: Each chat has its own dedicated directory and `GEMINI.md` file, providing long-term memory across sessions.
- **SQLite Database Backend**: Message history, session mappings, and scheduled tasks are stored in a robust SQLite database.
- **Natural Language Task Scheduler**: Use `/schedule <minutes> <prompt>` to have Gemini perform tasks in the future.
- **Integrated Web Access**: Gemini can autonomously search the web (via DuckDuckGo) and fetch text content from URLs.
- **OAuth Subscription Support**: Leverages your existing authenticated Gemini CLI session to use your Gemini Pro subscription.
- **Automated Approval (YOLO Mode)**: The bot runs in "yolo" mode, allowing Gemini to execute tools and commands autonomously to fulfill your requests.

## Setup Guide for Beginners

### 1. Create your Telegram Bot
If you don't have a bot yet, you need to create one via Telegram:
1.  Open Telegram and search for **@BotFather**.
2.  Send the command `/newbot`.
3.  Follow the instructions to name your bot and give it a username.
4.  BotFather will provide an **API Token** (e.g., `123456789:ABCdefGHI...`). **Save this token securely.**

### 2. Find your Telegram User ID
For security, this bot only responds to you. You need your numeric User ID:
1.  Search for **@userinfobot** in Telegram.
2.  Send any message to it.
3.  It will reply with your `Id` (e.g., `1234567890`). **Copy this ID.**

### 3. Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/skamphax0r/gemini_telegram.git
    cd gemini_telegram
    ```

2.  **Run Installer**:
    The installer will build the container image, set up the systemd service, and interactively help you create a `.env` file using the Token and ID you found above.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

3.  **Start the Service**:
    ```bash
    sudo systemctl start gemini-telegram-bot.service
    ```

## Usage & Bot Commands

Once the bot is running, start a chat with it on Telegram.

- `/status`: Check system health, uptime, and versions.
- `/start`: Initialize the orchestrator for your chat.
- `/clear`: Reset the current Gemini session context (start a fresh conversation).
- `/memory`: Read the current `GEMINI.md` memory file for this chat.
- `/memory <text>`: Manually update the persistent memory file.
- `/schedule <minutes> <prompt>`: Schedule a task (e.g., `/schedule 60 check the news for any updates on SpaceX`).

### How "YOLO" Mode Works
The bot utilizes the Gemini CLI's `--approval-mode yolo` flag. This means:
- When you ask a question that requires searching the web, Gemini will run the search tool automatically.
- If you ask Gemini to write a script or perform a calculation, it can execute those commands in its isolated container without asking for your permission each time.
- **Safety**: Because this runs inside a container, it cannot access your host filesystem (except for the specific workspace folder and your OAuth credentials).

---
*Built with Gemini CLI.*
