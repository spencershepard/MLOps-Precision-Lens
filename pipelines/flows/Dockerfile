FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
# Remove Windows-specific dependencies before installing
RUN grep -v "pywin32" requirements.txt > requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY . .
CMD ["python", "-V"]
