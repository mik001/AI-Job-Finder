# Dockerfile per AI Job Finder (Streamlit UI & Background Scheduler)
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Configura timezone Europa/Roma e pacchetti essenziali
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Rome
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    ca-certificates \
    xvfb \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Copia i requisiti e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium && \
    python -m camoufox fetch

# Copia il codice sorgente del progetto
COPY . .

# Variabili d'ambiente per Python, Playwright e Streamlit
ENV PYTHONPATH=.
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# Default CMD: schedulatore di background (sovrascrivibile da docker-compose)
CMD ["python", "src/scheduler.py"]
