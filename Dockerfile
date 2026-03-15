FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2, Pillow, and Remotion (Node.js)
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
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

# Install Node.js 20 for Remotion rendering
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
