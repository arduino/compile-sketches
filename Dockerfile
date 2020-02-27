# Container image that runs your code
FROM ubuntu:latest

# Install prerequisites
RUN apt-get update --quiet=2 && apt-get install --quiet=2 -y wget
CMD /bin/bash

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY entrypoint.sh /entrypoint.sh

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["/entrypoint.sh"]
