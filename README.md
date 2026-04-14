# Gemini Telegram Bot (NanoClaw-Style)

A high-performance, secure, and persistent Telegram bot interface for Gemini AI, inspired by the NanoClaw architecture.

## Key Features

- **Container Isolation**: All Gemini processing and tool execution (shell commands, web searches) run in isolated Docker/Podman containers.
- **Persistent Workspace Memory**: Each chat has its own dedicated directory and `GEMINI.md` file, providing long-term memory across sessions.
- **SQLite Database Backend**: Message history, session mappings, and scheduled tasks are stored in a robust SQLite database.
- **Natural Language Task Scheduler**: Use `/schedule <minutes> <prompt>` to have Gemini perform tasks in the future.
- **Integrated Web Access**: Gemini can autonomously search the web (via DuckDuckGo) and fetch text content from URLs.
- **OAuth Subscription Support**: Leverages your existing authenticated Gemini CLI session to use your Gemini Pro subscription.

## Architecture

```text
[Telegram] <-> [TelegramChannel] <-> [Orchestrator] <-> [SQLite DB]
                                          |
                                          v
                                  [ContainerRunner]
                                          |
                                          v
                                  [Gemini Agent (Isolated)]
                                  (Mounted ~/.gemini & Workspace)
```

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/skamphax0r/gemini_telegram.git
    cd gemini_telegram
    ```

2.  **Configure Environment**:
    Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and set:
    - `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather.
    - `ALLOWED_USER_ID`: Your Telegram User ID (to restrict access).

3.  **Run Installer**:
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

4.  **Start the Service**:
    ```bash
    sudo systemctl start gemini-telegram-bot.service
    ```

## Bot Commands

- `/status`: Check system health.
- `/start`: Initialize the orchestrator.
- `/clear`: Reset the current Gemini session context.
- `/memory`: Read the current `GEMINI.md` memory file.
- `/memory <text>`: Manually update the memory file.
- `/schedule <minutes> <prompt>`: Schedule a task for the future.

---
*Built with Gemini CLI.*
