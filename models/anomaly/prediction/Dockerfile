FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN apt-get update && apt-get install -y git
RUN grep -v "pywin32" requirements.txt > requirements-docker.txt
RUN grep -v "pywinpty" requirements-docker.txt > requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt
RUN apt-get update && apt-get install -y --no-install-recommends git
EXPOSE 8000
CMD ["python", "-u", "predict.py"] 