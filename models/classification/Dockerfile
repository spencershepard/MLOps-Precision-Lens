FROM python:3.13.5-slim
COPY . /app
WORKDIR /app
RUN grep -v "pywin32" requirements.txt > requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt
RUN apt-get update && apt-get install -y --no-install-recommends git
# Force unbuffered output
CMD ["python", "-u", "train.py"] 