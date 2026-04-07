FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/ gateway/

RUN mkdir -p /data/certs

ENV NIFI_MCP_STATE_FILE=/data/nifi_state.json
ENV NIFI_MCP_PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:'+os.environ.get('NIFI_MCP_PORT','8080')+'/health')" || exit 1

CMD ["python", "-m", "gateway"]
