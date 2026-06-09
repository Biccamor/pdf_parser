FROM python:3.11-slim
ENV PYTHONBUFFERED=1

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /parser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--timeout-keep-alive", "1000"]
