FROM python:3.11-slim

# Install system dependencies, libsecret and dbus for AGY keyring integration
RUN apt-get update && apt-get install -y \
    curl \
    git \
    gnupg \
    nodejs \
    npm \
    libsecret-1-0 \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Install common python packages
RUN pip install --no-cache-dir \
    requests \
    google-generativeai \
    python-dotenv \
    beautifulsoup4 \
    lxml \
    duckduckgo_search

# Set path
ENV PATH="/usr/local/bin:${PATH}"
ENV AGY_CLI_TRUST_WORKSPACE=true
ENV GEMINI_CLI_TRUST_WORKSPACE=true

# Entrypoint script
CMD ["python", "/app/agent.py"]

