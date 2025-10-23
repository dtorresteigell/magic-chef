# Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

# Gunicorn for production
CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:$PORT wsgi:app"]
