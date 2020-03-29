FROM python:3.8.2

# Install prerequisites
RUN apt-get update && apt-get install -y git wget jq curl \
    && rm -rf /var/lib/apt/lists/*

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY entrypoint.sh /entrypoint.sh
COPY reportsizetrends /reportsizetrends

# Install python dependencies
RUN pip install -r /reportsizetrends/requirements.txt

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["/entrypoint.sh"]
