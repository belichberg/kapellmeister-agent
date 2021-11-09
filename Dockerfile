# basic image
FROM python:3.9-slim-buster as base

# buffered
ENV PYTHONUNBUFFERED=1

# Add steps for requirements
FROM base as requirements

# Copy requirements.txt
COPY requirements.txt /tmp/requirements.txt

# install requirement packages from files
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Add steps for entrypoint
FROM requirements as source

# Set working directory to /app
WORKDIR /app

# copy all files to containers (ignore .dockerignore)
COPY . .

# run you command with Optimization and buffered output
CMD ["/usr/local/bin/python", "-u", "kapellmeister-agent.py"]
