# Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make sure entrypoint is executable
RUN chmod +x ./entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

# Run the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
