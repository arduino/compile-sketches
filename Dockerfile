FROM python:3.8.3

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY compilesketches /compilesketches

# Install python dependencies
RUN pip install -r /compilesketches/requirements.txt

# Code file to execute when the docker container starts up
ENTRYPOINT ["python", "/compilesketches/compilesketches.py"]
