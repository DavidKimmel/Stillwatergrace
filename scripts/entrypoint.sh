#!/usr/bin/env bash
set -e

echo "=== StillWaterGrace entrypoint ==="

# Wait for Postgres to be ready
until pg_isready -h db -U faithpage -q 2>/dev/null; do
  echo "Waiting for Postgres..."
  sleep 1
done
echo "Postgres is ready."

# Only the API service runs migrations (avoid race conditions with workers)
if echo "$@" | grep -q "uvicorn"; then
  echo "Running database migrations..."
  alembic upgrade head
  echo "Migrations complete."
else
  # Workers wait a few seconds for API to finish migrations
  echo "Worker mode — waiting for migrations to complete..."
  sleep 5
fi

# Execute the CMD passed to docker (uvicorn, celery, etc.)
echo "Starting: $@"
exec "$@"
