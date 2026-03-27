FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /parser

COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

ENV HF_HOME=/root/.cache/huggingface

# Pobierz modele przy buildzie - będą w image
RUN python -c "from marker.models import create_model_dict; create_model_dict()"

COPY . .

EXPOSE 8010