FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY example/template ./data/template
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data/uploads /app/data/logs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
