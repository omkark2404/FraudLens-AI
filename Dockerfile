# Use official Python 3.9 slim image (stable for ML dependencies)
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install necessary system libraries for OCR/OpenCV
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set necessary environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Expose the default port
EXPOSE 10000

# Start the application using Gunicorn (1 worker, 4 threads for concurrent background OCR)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 app:app"]
