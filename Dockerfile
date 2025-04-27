FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      libportaudio2 libportaudiocpp0 portaudio19-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY spike_cli/ ./spike_cli/
COPY config.yml ./
COPY .env . 

ENTRYPOINT ["python", "-m", "spike_cli.main"]