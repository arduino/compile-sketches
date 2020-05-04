FROM python:3.8.2

ENV PYTHONPATH="/reportsizetrends"

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY compilesketches /compilesketches
COPY reportsizetrends /reportsizetrends

# Install python dependencies
RUN pip install -r /compilesketches/requirements.txt
RUN pip install -r /reportsizetrends/requirements.txt

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["python", "/compilesketches/compilesketches.py"]
