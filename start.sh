#!/bin/bash
# Do NOT use set -e here — we want the server to start even if migration fails

echo "=== Contemplation Flow Startup ==="

# Convert async DB URL to a psql-compatible one
DB_URL="${ASAM_DB_URL}"
DB_URL="${DB_URL/postgresql+asyncpg/postgresql}"

# -----------------------------------------------------------
# Step 1: Ensure critical auth columns exist (idempotent SQL)
# This runs BEFORE alembic and guarantees the schema is ready
# even if alembic has issues with revision chains.
# -----------------------------------------------------------
echo "Step 1: Ensuring auth columns exist via direct SQL..."
if [ -n "$DB_URL" ]; then
  psql "$DB_URL" <<'EOSQL'
-- Ensure email column exists
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS email VARCHAR;

-- Ensure password_hash column exists
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS password_hash VARCHAR;

-- Make phone_number nullable (safe even if already nullable)
DO $$
BEGIN
  ALTER TABLE user_profiles ALTER COLUMN phone_number DROP NOT NULL;
EXCEPTION WHEN OTHERS THEN
  -- Already nullable, ignore
  NULL;
END $$;

-- Create indexes idempotently
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profile_email
  ON user_profiles (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_profile_email
  ON user_profiles (email);
EOSQL
  SQL_EXIT=$?
  if [ $SQL_EXIT -eq 0 ]; then
    echo "✅ Auth columns verified/created."
  else
    echo "⚠️  Direct SQL column check failed (exit $SQL_EXIT). Continuing..."
  fi
else
  echo "⚠️  ASAM_DB_URL not set — skipping direct SQL check."
fi

# -----------------------------------------------------------
# Step 2: Run alembic migrations (handles any other migrations)
# -----------------------------------------------------------
echo "Step 2: Running alembic migrations..."
alembic upgrade head
MIGRATION_EXIT=$?
if [ $MIGRATION_EXIT -ne 0 ]; then
  echo "⚠️  Alembic migration exited with code $MIGRATION_EXIT."
  echo "    Auth columns were already ensured in Step 1."

  # Try to stamp alembic so future runs don't fail
  if [ -n "$DB_URL" ]; then
    echo "    Stamping alembic version..."
    psql "$DB_URL" -c \
      "INSERT INTO alembic_version (version_num) VALUES ('add_email_password_auth') ON CONFLICT DO NOTHING;" \
      2>/dev/null || true
  fi
else
  echo "✅ Alembic migrations complete."
fi

# -----------------------------------------------------------
# Step 3: Start the server
# -----------------------------------------------------------
echo "Starting uvicorn server..."
exec uvicorn src.server:get_app --host 0.0.0.0 --port 8000 --factory
