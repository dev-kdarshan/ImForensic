FROM python:3.12-slim
WORKDIR /app
ARG ENABLE_DDA=false
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY requirements-model.txt .
RUN if [ "$ENABLE_DDA" = "true" ]; then \
      pip install --no-cache-dir --index-url "$TORCH_INDEX_URL" torch==2.6.0 torchvision==0.21.0 && \
      pip install --no-cache-dir -r requirements-model.txt; \
    fi
COPY app ./app
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
