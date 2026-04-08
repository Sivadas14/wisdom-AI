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

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

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

# Install dependencies into the virtual environment.
# NOTE: --frozen removed intentionally: the lockfile is out of sync with
# pyproject.toml (razorpay was added to pyproject.toml but uv.lock was not
# regenerated). Without --frozen, uv will resolve missing packages from
# pyproject.toml at build time and install them correctly.
RUN uv sync --no-cache

# Copy backend application code
COPY backend/alembic.ini .
COPY backend/alembic ./alembic
COPY backend/src ./src

# Copy the built frontend from the first stage
COPY --from=frontend-builder /frontend/dist ./src/ui

# Change ownership to non-root user
# Change ownership to non-root user - using a more efficient approach
RUN chown -R appuser:appuser /app /home/appuser

# Switch to the non-root user
USER appuser

# Expose the port (informative only, App Runner ignores this)
EXPOSE 8000

# Command to run the application - using JSON form with shell execution for variable support
CMD ["sh", "-c", "uvicorn src.server:get_app --host 0.0.0.0 --port ${PORT:-8000} --factory"]