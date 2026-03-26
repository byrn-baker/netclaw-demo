FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY batfish_mcp_server.py .

ENV BATFISH_HOST=localhost
ENV BATFISH_PORT=9997
ENV BATFISH_NETWORK=netclaw

CMD ["python", "-u", "batfish_mcp_server.py"]
