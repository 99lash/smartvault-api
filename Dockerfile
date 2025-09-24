# Use Python 3.13 slim base image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (needed for things like psycopg2, Alembic, etc.)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (for better Docker caching)
COPY requirements.txt . 

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy example env file (for reference inside container)
COPY .env.example .env.example

# Copy the rest of the project files
COPY . .

# Expose FastAPI/UVicorn port
EXPOSE 8000

# Run the API using uvicorn (main app entry = app/main.py, variable = app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
