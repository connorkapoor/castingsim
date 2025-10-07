FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Gmsh and OpenGL
RUN apt-get update && apt-get install -y \
    libglu1-mesa \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p uploads results

EXPOSE 5000

CMD ["python", "app.py"]

