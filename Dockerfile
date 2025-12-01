# Use an official Python runtime as a parent image
# We use a slim image to keep the container size down
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
# We use --no-cache-dir to prevent caching package files, saving space.
# We also install 'gcc' and 'musl-dev' temporarily, as paramiko (via cryptography)
# often requires compilation tools, even in slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y build-essential libssl-dev libffi-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application source code into the container
# This includes app.py
COPY app.py .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run the app using the simple Flask built-in server (suitable for development)
# For production, you would use a WSGI server like Gunicorn.
CMD [ "python", "app.py" ]
