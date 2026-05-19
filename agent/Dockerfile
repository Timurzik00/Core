FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y docker.io && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/coroot_agent.py .

CMD ["python3", "coroot_agent.py"]
