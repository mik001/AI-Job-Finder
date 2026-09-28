# Dockerfile per AI Job Finder con Playwright & Chromium
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Copia i requisiti e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente
COPY . .

# Variabili d'ambiente per Python
ENV PYTHONPATH=.
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Esegui lo schedulatore automatico di background
CMD ["python", "src/scheduler.py"]
