FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
# Development only. Production ASGI/WSGI serving is added in deployment phase.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
