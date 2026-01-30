FROM python:3-slim

WORKDIR /app

COPY ./app .

RUN apt-get update && pip install -r requirements.txt 

RUN apt-get update && apt-get install -y \
    curl \
    wget \
    postgresql-client \ 
    iputils-ping \
    dnsutils \
    iproute2 \
    traceroute \
    vim \
    less \
    && rm -rf /var/lib/apt/lists/*

CMD ["python", "app.py"]
