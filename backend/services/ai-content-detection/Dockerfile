FROM python:3.12-slim

WORKDIR /app

ARG ENABLE_DDA=false
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG DINOV2_CODE_REVISION=7b187bd4df8efce2cbcbbb67bd01532c19bf4c9c

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY requirements-model.txt .

RUN if [ "$ENABLE_DDA" = "true" ]; then \
      pip install --no-cache-dir --index-url "$TORCH_INDEX_URL" torch==2.6.0 torchvision==0.21.0 && \
      pip install --no-cache-dir -r requirements-model.txt; \
    fi

RUN if [ "$ENABLE_DDA" = "true" ]; then \
      apt-get update && \
      apt-get install -y --no-install-recommends git && \
      git init /opt/dinov2 && \
      git -C /opt/dinov2 remote add origin https://github.com/facebookresearch/dinov2.git && \
      git -C /opt/dinov2 fetch --depth 1 origin "$DINOV2_CODE_REVISION" && \
      git -C /opt/dinov2 checkout --detach FETCH_HEAD && \
      test "$(git -C /opt/dinov2 rev-parse HEAD)" = "$DINOV2_CODE_REVISION" && \
      rm -rf /opt/dinov2/.git && \
      apt-get purge -y --auto-remove git && \
      rm -rf /var/lib/apt/lists/*; \
    fi

COPY app ./app

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]