FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/app \
    PORT=8000 \
    FINANCE_MCP_DATA_DIR=/app/data/finance_handoff \
    FINANCE_OFFICER_DATA_DIR=/app/data/finance_otp_officer \
    FINANCE_OTP_MCP_DATA_DIR=/app/data/finance_otp_officer \
    FINANCE_MCP_STATE_DIR=/app/state/finance-handoff \
    FINANCE_OTP_MCP_STATE_DIR=/app/state/finance-otp-officer

WORKDIR /app

COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY app ./app
COPY data ./data

FROM base AS test
COPY tests ./tests
COPY --from=handoff_agent agent.json /sample-contracts/finance-handoff.json
COPY --from=otp_agent agent.json /sample-contracts/finance-otp-officer.json
ENV SHARED_MCP_AGENT_CONTRACT_ROOT=/sample-contracts
RUN python -m unittest discover -s tests -v

FROM base AS runtime
RUN groupadd --system mcp \
    && useradd --system --gid mcp --home-dir /app mcp \
    && mkdir -p /app/state \
    && chown -R mcp:mcp /app/state

USER mcp
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]

CMD ["python", "-m", "shared_mcp.server"]
