FROM python:3.11.9-slim

# Instalujemy zależności systemowe dla grafiki (Marker/OpenCV tego potrzebują)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Tworzymy użytkownika, żeby nie pracować jako root (bezpieczeństwo!)
RUN groupadd -g 1000 user && useradd -u 1000 -g user -m user

# Przygotowujemy foldery ZANIM przełączymy się na użytkownika
RUN mkdir -p /home/user/.cache/huggingface /home/user/.cache/surya /parser && \
    chown -R 1000:1000 /home/user /parser

# Ustawiamy katalog roboczy
WORKDIR /parser

# Kopiujemy requirements i instalujemy paczki
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę kodu
COPY --chown=user:user . .

# Ważne zmienne środowiskowe dla AI
ENV HOME=/home/user
ENV HF_HOME=/home/user/.cache/huggingface

# Przełączamy się na użytkownika
USER user

# Port, na którym działa FastAPI
EXPOSE 8010