FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2, Pillow, Remotion (Node.js + Chrome headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    postgresql-client \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    ffmpeg \
    curl \
    # Chrome headless dependencies for Remotion rendering
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

# Install Node.js 20 for Remotion rendering
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright + Chromium for HTML-to-image rendering
# System deps already installed above; skip --with-deps to avoid missing font packages on Debian Trixie
RUN playwright install chromium

# Georgia-compatible font (Caladea)
RUN apt-get update && apt-get install -y fonts-crosextra-caladea && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
