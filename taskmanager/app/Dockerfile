# Use a slim Python 3.12 image.
FROM python:3.12-slim
# Set the container working directory.
WORKDIR /app
# Copy the Python dependency list.
COPY requirements.txt .
# Install Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt
# Copy the application into the image.
COPY app.py .
# Declare the application port.
EXPOSE 6000
# Start the application.
CMD ["python", "app.py"]
