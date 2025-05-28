# Use a lightweight Alpine image with Python
FROM python:3.9-alpine

# Set environment variable for the server port
ENV SERVER_PORT=8080

# Set the working directory
WORKDIR /app

# Copy your Python server script into the container
COPY server.py .

# Install only the required Python dependencies (if any)
RUN pip install --no-cache-dir Flask  # You can replace Flask with the packages you need

# Expose the port (same as the one used by the server)
EXPOSE $SERVER_PORT

# Run the Python server
CMD ["python", "server.py"]
