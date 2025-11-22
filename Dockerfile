# 1) Base Python (Debian slim pour limiter la taille)
FROM python:3.12-slim

# 2) Variables d'environnement Python
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 3) Installation des dépendances système (Tesseract, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    libtesseract-dev \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4) Répertoire de travail dans le conteneur
WORKDIR /app

# 5) Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6) Copie du code applicatif
COPY . .

# 7) Port exposé (FastAPI / uvicorn)
EXPOSE 8050

# 8) Commande de démarrage
#  --reload ?
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"] 
