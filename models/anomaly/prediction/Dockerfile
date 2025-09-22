FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

RUN grep -v -e "pywin32" -e "pywinpty" requirements.txt > requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt
EXPOSE 8000
CMD ["python", "-u", "predict.py"]