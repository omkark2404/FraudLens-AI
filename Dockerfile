# -- Build Stage --
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a local directory for copying
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# -- Runtime Stage --
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for OpenCV and PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Ensure the local bin is in PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy the application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=false
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Change ownership of the uploads and db directories if needed
RUN mkdir -p uploads && chown -R appuser:appuser uploads

# Switch to the non-root user
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
