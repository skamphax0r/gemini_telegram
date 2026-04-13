FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Install common python packages the agent might need
RUN pip install --no-cache-dir \
    requests \
    google-generativeai \
    python-dotenv

# Entrypoint script will be mounted/provided later
CMD ["python", "/app/agent.py"]
