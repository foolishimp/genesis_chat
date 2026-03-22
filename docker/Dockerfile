FROM python:3.11-slim

WORKDIR /app

# Install pyyaml (only external dep)
RUN pip install --no-cache-dir pyyaml

# Copy source
COPY builds/python/src/ ./src/
COPY agents.yml commands.yml workflow_bindings.yml adapters.yml ./

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "genesis_chat"]
