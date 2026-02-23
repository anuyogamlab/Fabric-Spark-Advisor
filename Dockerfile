# Multi-stage Docker build for Spark Recommender Agent
# Optimized for Azure Container Apps deployment

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY agent/ ./agent/
COPY mcp_server/ ./mcp_server/
COPY rag/ ./rag/
COPY ui/ ./ui/
COPY examples/ ./examples/
COPY run.py .
COPY .vscode/ ./.vscode/

# Create non-root user for security
RUN useradd -m -u 1000 sparkuser && \
    chown -R sparkuser:sparkuser /app

USER sparkuser

# Expose ports
# 8000 - MCP Server (SSE)
# 8501 - Chainlit UI
EXPOSE 8000 8501

# Environment variables with defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/ || exit 1

# Startup script
CMD ["python", "run.py"]
