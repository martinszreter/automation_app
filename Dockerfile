FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import asyncpg; print('asyncpg OK')" \
    && python -c "import psycopg2; print('psycopg2 OK')"

COPY . .

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
