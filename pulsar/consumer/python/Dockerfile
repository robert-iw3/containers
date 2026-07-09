FROM python:3.13-slim-bookworm
WORKDIR /usr/src/app
RUN pip install --no-cache-dir pulsar-client
COPY . .
CMD [ "python", "./consumer.py" ]