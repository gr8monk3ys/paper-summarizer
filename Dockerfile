FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
ARG LOCAL_MODELS=false
ENV LOCAL_MODELS=${LOCAL_MODELS}
RUN if [ "$LOCAL_MODELS" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra local; \
    else \
      uv sync --frozen --no-dev --no-install-project; \
    fi

# Copy application code
COPY . .

# Ensure README exists for build metadata
RUN if [ ! -f README.md ]; then echo "# Paper Summarizer" > README.md; fi

# Install the project
RUN if [ "$LOCAL_MODELS" = "true" ]; then \
      uv sync --frozen --no-dev --extra local; \
    else \
      uv sync --frozen --no-dev; \
    fi

# Create uploads directory
RUN mkdir -p uploads

# Railway injects PORT at runtime; default to 5000 for local dev
ENV PORT=5000
EXPOSE ${PORT}

# Health check
HEALTHCHECK CMD curl --fail http://localhost:${PORT}/health || exit 1

# Run FastAPI — uses shell form so $PORT is expanded at runtime
CMD uv run uvicorn paper_summarizer.web.app:app --host 0.0.0.0 --port $PORT
