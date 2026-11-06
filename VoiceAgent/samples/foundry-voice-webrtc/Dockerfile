FROM python:3.12-alpine

LABEL com.azure.containerizationassist.createdby="containerization-assist"

ARG PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.txt \
    && adduser -D -u 10001 appuser

COPY auth.py check_websocket.py server.py ./
COPY public ./public

EXPOSE 8080

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"]

CMD ["python", "server.py"]