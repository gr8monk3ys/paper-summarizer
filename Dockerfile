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

# Expose app port
EXPOSE 5000

# Health check
HEALTHCHECK CMD curl --fail http://localhost:5000/health || exit 1

# Run FastAPI
CMD ["uv", "run", "uvicorn", "paper_summarizer.web.app:app", "--host", "0.0.0.0", "--port", "5000"]
