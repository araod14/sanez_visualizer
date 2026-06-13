FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir . && mkdir -p static/uploads

EXPOSE 8000

# Aplica migraciones pendientes antes de arrancar (no-op si la DB ya está en head).
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
