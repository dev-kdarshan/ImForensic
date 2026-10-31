FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY backend/evidence-correlation/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/evidence-correlation/app /app/app
COPY backend/shared /app/shared
EXPOSE 8008
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
