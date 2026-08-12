FROM python:3.12-slim

ARG BUILD_TIME
ARG GIT_SHA
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_BUILD_TIME=$BUILD_TIME \
    APP_GIT_SHA=$GIT_SHA
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data/uploads /app/data/logs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
