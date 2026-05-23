FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir \
    scapy>=2.5.0 \
    networkx>=3.0

# Install mcp and fastmcp from PyPI
RUN pip install --no-cache-dir \
    mcp>=1.0.0 \
    fastmcp>=0.1.0

# Copy the protocol-mcp source code
COPY . .

# Expose the MCP server port (if needed)
EXPOSE 9000

# Run the protocol-mcp server
CMD ["python", "server.py"]