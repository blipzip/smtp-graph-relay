FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt


FROM python:3.13-slim

RUN useradd -r -u 10001 -g nogroup appuser

WORKDIR /app

COPY --from=builder /wheels /wheels

RUN pip install --no-cache /wheels/* && rm -rf /wheels

COPY smtp-graph-relay.py .

USER appuser

EXPOSE 8587

ENV PYTHONUNBUFFERED=1

CMD ["python", "smtp-graph-relay.py"]
