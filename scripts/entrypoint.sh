#!/usr/bin/env bash
set -e

echo "=== StillWaterGrace entrypoint ==="

# Wait for Postgres to be ready
until pg_isready -h db -U faithpage -q 2>/dev/null; do
  echo "Waiting for Postgres..."
  sleep 1
done
echo "Postgres is ready."

# Install ReelCreate if available (mounted at /reelcreate)
if [ -d "/reelcreate" ] && [ -f "/reelcreate/pyproject.toml" ]; then
  echo "Installing ReelCreate..."
  pip install -q -e /reelcreate 2>/dev/null || echo "ReelCreate install skipped"

  # Install Remotion npm packages (rebuild if native bindings are for wrong platform)
  if [ -d "/reelcreate/rendering/remotion" ]; then
    REMOTION_DIR="/reelcreate/rendering/remotion"
    RSPACK_LINUX="$REMOTION_DIR/node_modules/@rspack/binding-linux-x64-gnu"
    if [ ! -d "$REMOTION_DIR/node_modules/remotion" ] || [ ! -d "$RSPACK_LINUX" ]; then
      echo "Installing Remotion dependencies (Linux bindings)..."
      cd "$REMOTION_DIR" && npm install --silent 2>/dev/null || echo "Remotion install skipped"
      cd /app
    else
      echo "Remotion dependencies OK (Linux bindings present)."
    fi
  fi
fi

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
