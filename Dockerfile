# One image for both background services (see docker-compose.yml): the voice agent and the worker.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# tzdata: the worker runs the morning job at 06:00 local time (config/config.yaml).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY config ./config
COPY schema ./schema
COPY samples ./samples
COPY agent ./agent
COPY pipeline ./pipeline
COPY worker ./worker
