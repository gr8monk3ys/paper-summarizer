FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.2

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Configure Poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Copy application code
COPY . .

# Install the project
RUN poetry install --no-interaction --no-ansi --only main

# Create uploads directory
RUN mkdir -p uploads

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK CMD curl --fail http://localhost:5000/health || exit 1

# Run Flask
CMD ["python", "run.py"]
