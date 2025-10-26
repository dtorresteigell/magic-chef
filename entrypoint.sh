#!/bin/sh
echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:$PORT "app:create_app()"
