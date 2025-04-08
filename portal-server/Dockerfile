FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg &&     apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install numpy pymongo pyfeclib kubernetes requests

COPY . .

CMD ["python", "portal_server.py"]
