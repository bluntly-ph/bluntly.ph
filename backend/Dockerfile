FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; psycopg[binary] ships its own libpq.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Default command runs the API; docker-compose overrides for worker/beat.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
