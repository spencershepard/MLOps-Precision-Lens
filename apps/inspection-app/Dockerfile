FROM python:3.12

WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --upgrade pip
# Remove Windows-specific dependencies before installing
RUN grep -v "pywin32" requirements.txt > requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt
EXPOSE 8050
ENV FLASK_APP=main.py
ENV DASH_DEBUG=false

CMD ["python", "main.py"]
