# Use Python 3.12 as base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# Optional: Use Tsinghua University mirror for faster downloads in China
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager (recommended fast Python package manager)
# Using pip with Tsinghua University mirror for faster downloads
RUN pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy project files
COPY pyproject.toml ./
COPY LICENSE ./

# Copy source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY Vitos-Pizza-Cafe-KB/ ./Vitos-Pizza-Cafe-KB/
COPY customer_db.sql ./

# Copy startup scripts
COPY start_backend.sh ./
COPY start_frontend.sh ./

# Give startup scripts execute permissions
RUN chmod +x *.sh

# Create virtual environment and install dependencies
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

# Activate virtual environment and install project dependencies
RUN . .venv/bin/activate && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .

# Create example .env file (users need to provide actual API keys at runtime)
COPY .env.example .env.example

# Create logs directory
RUN mkdir -p logs

# Expose ports
# 8000 - Backend API port
# 5500 - Frontend web interface port
EXPOSE 8000 5500

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Startup command - start both backend and frontend
CMD ["/bin/bash", "-c", "source .venv/bin/activate && ./start_backend.sh && ./start_frontend.sh && tail -f logs/*.log"]