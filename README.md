# AGY Telegram Bot (NanoClaw-Style)

A high-performance, secure, and persistent Telegram bot interface for Antigravity (AGY), inspired by the NanoClaw architecture.

## Key Features

- **Container Isolation**: All AGY processing and tool execution (shell commands, web searches) run in isolated Docker/Podman containers.
- **Persistent Workspace Memory**: Each chat has its own dedicated directory and `AGY.md` (or `GEMINI.md`) file, providing long-term memory across sessions.
- **SQLite Database Backend**: Message history, session mappings, and scheduled tasks are stored in a robust SQLite database (`agy_bot.db`).
- **Natural Language Task Scheduler**: Use `/schedule <minutes> <prompt>` to have AGY perform tasks in the future.
- **Integrated Web Access**: AGY can autonomously search the web and fetch content from URLs.
- **Authentication & Subscription Support**: Integrates with your authenticated AGY CLI session to access Antigravity models.
- **Automated Approval**: The bot runs with `--dangerously-skip-permissions` in its isolated container, allowing AGY to execute tools and commands autonomously to fulfill your requests.

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

2.  **Ensure AGY CLI is installed**:
    Ensure `agy` is available in your PATH (e.g., `agy --version`).

3.  **Run Installer**:
    The installer will build the container image, set up the systemd service, and configure dependencies.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

4.  **Configure Environment**:
    Create or edit `.env` in the project root:
    ```env
    TELEGRAM_BOT_TOKEN="your_bot_token_here"
    ALLOWED_USER_ID="your_telegram_user_id_here"
    ```

5.  **Start the Service**:
    ```bash
    sudo systemctl start agy-telegram-bot.service
    ```

## Usage & Bot Commands

Once the bot is running, start a chat with it on Telegram.

- `/status`: Check system health, uptime, Python version, and AGY CLI version.
- `/start`: Initialize the orchestrator for your chat.
- `/clear`: Reset the current AGY conversation session context (start a fresh conversation).
- `/memory`: Read the current `AGY.md` memory file for this chat.
- `/memory <text>`: Manually update the persistent memory file.
- `/schedule <minutes> <prompt>`: Schedule a task (e.g., `/schedule 60 check the news for any updates on SpaceX`).

### Autonomous Tool Execution
The bot utilizes the AGY CLI's `--dangerously-skip-permissions` flag within the container environment. This means:
- When you ask a question that requires searching the web or executing commands, AGY will run the tools automatically.
- If you ask AGY to write a script or perform a calculation, it executes those commands in its isolated container without requiring manual prompt confirmations.
- **Safety**: Because this runs inside a container, it cannot access arbitrary host files outside the designated mounts.

---
*Built with Antigravity CLI (`agy`).*

