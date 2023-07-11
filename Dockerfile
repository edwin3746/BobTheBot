# Use Ubuntu 20.04 as the base image
FROM ubuntu:20.04
ARG DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /app

# Update the package lists and install Python, pip, and ClamAV
RUN apt-get update && apt-get install -y python3 python3-pip clamav


# Copy only the necessary files to the Docker container
COPY app.py /app/
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN freshclam

# Expose any required ports
EXPOSE 5000 3310

# Set the command to run your application
CMD ["python3", "app.py"]
