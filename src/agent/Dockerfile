FROM python:3.11-slim

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    git \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Install common python packages
RUN pip install --no-cache-dir \
    requests \
    google-generativeai \
    python-dotenv

# Install gemini CLI via npm
RUN npm install -g @google/gemini-cli

# Set path (npm global bin is usually in /usr/bin or /usr/local/bin)
ENV PATH="/usr/local/bin:${PATH}"

# Entrypoint script
CMD ["python", "/app/agent.py"]
