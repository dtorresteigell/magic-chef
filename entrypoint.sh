#!/bin/sh
set -e  # stop on first error

echo "Running database migrations..."
flask db upgrade || { echo "❌ Migration failed!"; exit 1; }

echo "✅ Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:$PORT app:create_app

