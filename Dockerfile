# Use an official, lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for building uvloop and motor
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your bot's code into the container
COPY . .

# Expose the port for your dummy web server (Important for Render/Koyeb)
EXPOSE 8080

# The command to start your ultra-fast bot
CMD ["python", "bot.py"]
