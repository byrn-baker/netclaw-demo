FROM python:3.12-slim

LABEL maintainer="NetClaw" \
      description="ContainerLab MCP Server" \
      version="0.1.0"

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY containerlab_mcp_server.py .

# Run as non-root user
RUN useradd -m -r clab && chown -R clab:clab /app
USER clab

# Default entrypoint: stdio transport
ENTRYPOINT ["python", "-u", "containerlab_mcp_server.py"]
