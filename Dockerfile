FROM python:3.11.9-slim

WORKDIR /parser

RUN apt-get update && apt-get install -y \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /parser/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /parser/requirements.txt

RUN python -c "from marker.util import download_font; download_font()"

RUN useradd -m user
COPY --chown=user:user . /parser/

USER user 

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1"]