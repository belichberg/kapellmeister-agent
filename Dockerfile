# basic image
FROM python:3.9-alpine3.12 as base

# Add steps for requirements
FROM base as requirements

# Copy requirements.txt
COPY requirements.txt /tmp/requirements.txt

# update pip
RUN pip install --upgrade pip

# install requirement packages from files and purge cache
RUN pip install --user --no-cache-dir -r /tmp/requirements.txt && pip cache purge

# Add steps for entrypoint
FROM requirements as source

# add local root path
ENV PATH=/root/.local/bin:$PATH

# buffered
ENV PYTHONUNBUFFERED=1

# Set working directory to /app
WORKDIR /app

# copy all files to containers (ignore .dockerignore)
COPY . .

# run you command with Optimization and buffered output
CMD ["/usr/local/bin/python", "-u", "kapellmeister-agent.py"]
