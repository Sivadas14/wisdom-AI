#!/bin/bash
# Do NOT use set -e here — we want the server to start even if migration fails

echo "=== Contemplation Flow Startup ==="

# Convert async DB URL to a psql-compatible one
DB_URL="${ASAM_DB_URL}"
DB_URL="${DB_URL/postgresql+asyncpg/postgresql}"

# -----------------------------------------------------------
# Step 1: Ensure ALL required columns exist (idempotent SQL)
# This guarantees the schema matches what the SQLAlchemy model
# expects, regardless of which alembic migrations ran before.
# -----------------------------------------------------------
echo "Step 1: Ensuring all required columns exist via direct SQL..."
if [ -n "$DB_URL" ]; then
  psql "$DB_URL" <<'EOSQL'
-- =====================================================
-- Ensure user_profiles has ALL columns the ORM expects
-- =====================================================

-- Auth columns
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS email VARCHAR;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS password_hash VARCHAR;

-- Profile columns
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS name VARCHAR;

-- Phone columns (legacy, kept for backward compat)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE;

-- Session tracking
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_signed_in BOOLEAN DEFAULT FALSE NOT NULL;

-- Timestamps (may already exist from original schema)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Make phone_number nullable (safe even if already nullable)
DO $$
BEGIN
  ALTER TABLE user_profiles ALTER COLUMN phone_number DROP NOT NULL;
EXCEPTION WHEN OTHERS THEN
  NULL;
END $$;

-- Ensure role enum type exists
DO $$
BEGIN
  CREATE TYPE user_role_enum AS ENUM ('user', 'admin');
EXCEPTION WHEN duplicate_object THEN
  NULL;
END $$;

-- Add role column if missing
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS role user_role_enum DEFAULT 'user';

-- Create indexes idempotently
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profile_email
  ON user_profiles (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_profile_email
  ON user_profiles (email);
CREATE INDEX IF NOT EXISTS idx_user_profile_phone
  ON user_profiles (phone_number);
CREATE INDEX IF NOT EXISTS idx_user_profile_role
  ON user_profiles (role);
CREATE INDEX IF NOT EXISTS idx_user_profile_last_active
  ON user_profiles (last_active_at);

-- Set defaults for any NULL is_signed_in values
UPDATE user_profiles SET is_signed_in = FALSE WHERE is_signed_in IS NULL;
UPDATE user_profiles SET phone_verified = FALSE WHERE phone_verified IS NULL;

EOSQL
  SQL_EXIT=$?
  if [ $SQL_EXIT -eq 0 ]; then
    echo "✅ All required columns verified/created."
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
  echo "    Required columns were already ensured in Step 1."
else
  echo "✅ Alembic migrations complete."
fi

# -----------------------------------------------------------
# Step 3: Start the server
# -----------------------------------------------------------
echo "Starting uvicorn server..."
exec uvicorn src.server:get_app --host 0.0.0.0 --port 8000 --factory
