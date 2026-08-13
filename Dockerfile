# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend package files
COPY frontend/package*.json ./
COPY frontend/bun.lockb ./

# Increase npm resilience for network issues
RUN npm config set fetch-retry-maxtimeout 600000 && \
    npm config set fetch-retry-mintimeout 10000 && \
    npm config set fetch-retries 5 && \
    npm config set progress false && \
    npm config set registry https://registry.npmjs.org/

# Install frontend dependencies
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Add build arguments for frontend environment variables
ARG VITE_API_BASE_URL=/api
ARG VITE_SUPABASE_URL=https://jmmqzddkwsmwdczwtrwq.supabase.co
ARG VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImptbXF6ZGRrd3Ntd2Rjend0cndxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk3NDQ3NTAsImV4cCI6MjA4NTMyMDc1MH0.NRqYCh6j1VmIPckh3S2Tcs5f9xNo9n5Nr1khohlVTU8
    
# Set environment variables for the build process
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL    
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
# Build the frontend
RUN npm run build

# Stage 2: Build the final backend image with frontend
FROM python:3.11-slim

# Accept git SHA so the health endpoint can report which version is running
ARG GIT_SHA=unknown

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    GIT_SHA=$GIT_SHA

# Install uv from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies required by your application
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Set the working directory
WORKDIR /app

# Copy backend dependency definitions
COPY backend/pyproject.toml backend/uv.lock ./

# Step 1: Regenerate the lockfile so it always reflects pyproject.toml exactly.
# The committed uv.lock can fall behind when dependencies change (e.g. tuneapi
# removed and anthropic added). Running uv lock first makes the subsequent sync
# fully deterministic regardless of the committed lockfile state.
RUN uv lock

# Step 2: Install from the now-accurate lockfile.
RUN uv sync --no-cache --frozen

# Copy backend application code
COPY backend/alembic.ini .
COPY backend/alembic ./alembic
COPY backend/src ./src

# Copy the built frontend from the first stage
COPY --from=frontend-builder /frontend/dist ./src/ui

# Smoke test: verify the server factory can be imported and initialised.
# This runs get_app() so any startup crash (missing module, bad attribute, etc.)
# fails the Docker BUILD with a visible error rather than silently crashing the
# container at runtime.
RUN python3 -c "
import sys, os
sys.path.insert(0, '.')
# Provide enough env to let Settings construct without crashing
os.environ.setdefault('ASAM_DB_URL', 'postgresql+asyncpg://x:x@localhost/x')
os.environ.setdefault('ASAM_JWT_SECRET', 'smoke-test-secret')
from src.server import get_app
app = get_app()
print('[SMOKE TEST] get_app() succeeded — server startup is clean.')
" 2>&1 | tee /tmp/smoke.log || (cat /tmp/smoke.log && exit 1)

# Change ownership to non-root user
# Change ownership to non-root user - using a more efficient approach
RUN chown -R appuser:appuser /app /home/appuser

# Switch to the non-root user
USER appuser

# Expose the port (informative only, App Runner ignores this)
EXPOSE 8000

# Command to run the application - using JSON form with shell execution for variable support
CMD ["sh", "-c", "uvicorn src.server:get_app --host 0.0.0.0 --port ${PORT:-8000} --factory"]