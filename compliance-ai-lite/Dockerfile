FROM python:3.12-slim

# Install OS dependencies required for building C-extensions like cryptography/pdfplumber
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    rustc \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency file and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Expose port (Render automatically assigns $PORT)
EXPOSE 8000

# Start server using the standard Render/production command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
