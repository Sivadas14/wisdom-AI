#!/bin/bash
# Do NOT use set -e here — we want the server to start even if migration fails

echo "=== Contemplation Flow Startup ==="

echo "Running database migrations..."
alembic upgrade head
MIGRATION_EXIT=$?
if [ $MIGRATION_EXIT -ne 0 ]; then
  echo "⚠️  Migration exited with code $MIGRATION_EXIT — server will still start."
  echo "    Check DB connectivity and migration logs in App Runner console."
else
  echo "✅ Migrations complete."
fi

echo "Starting uvicorn server..."
exec uvicorn src.server:get_app --host 0.0.0.0 --port 8000 --factory
