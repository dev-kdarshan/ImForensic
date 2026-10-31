# ImForensic

ImForensic is a modular image-forensics project for examining metadata, provenance indicators, and other digital-image evidence.

## Implemented vertical slice

- React/Vite upload interface connected to the API Gateway.
- FastAPI Gateway validates JPEG, PNG, and WebP uploads, computes SHA-256, stores files privately, and persists analysis records in SQLite.
- Metadata & Provenance service extracts image dimensions, format, mode, EXIF, selected embedded metadata, software/XMP signals, and interpretation limitations.
- Model Fingerprinting service extracts deterministic descriptive features: channel statistics/histograms/entropy, grayscale entropy/histogram, a simple edge-response statistic, and coarse spatial luminance measurements.
- The Gateway sends the same uploaded bytes to both engines over internal HTTP, verifies each returned SHA-256, and persists independent per-engine results. One engine failure does not discard the other engine's result.
- Docker Compose includes the Gateway, Metadata & Provenance, Model Fingerprinting, Kafka, PostgreSQL, and Redis services.

**Scientific limitation:** Model Fingerprinting is not a trained generator classifier. It returns an inconclusive attribution outcome and does not provide model identification, candidate rankings, or calibrated probabilities. No labelled reference dataset or model weights are included. See the Model Fingerprinting documentation in docs/model-fingerprinting.md.

Kafka asynchronous orchestration, the remaining four forensic engines, evidence correlation, SSE progress, C2PA signature verification, and AI-generation classification are not yet implemented. PostgreSQL and Redis are infrastructure services; the current Gateway persistence is SQLite.

## Run with Docker

From the repository root:

    docker compose -f infrastructure/docker-compose.yml up --build

- API Gateway: http://localhost:8000 (API docs at /docs)
- Metadata engine: http://localhost:8001/docs
- Model Fingerprinting engine: http://localhost:8002/docs

Run the frontend separately:

    cd frontend
    npm install
    npm run dev

Set VITE_API_BASE_URL=http://localhost:8000 in frontend/.env if required.

## Run backend services locally

Start Metadata on port 8001 and Model Fingerprinting on port 8002 using their service directories and documented requirements. Then start the Gateway:

    cd backend/api-gateway
    python -m pip install -r requirements.txt
    METADATA_SERVICE_URL=http://127.0.0.1:8001 MODEL_FINGERPRINT_SERVICE_URL=http://127.0.0.1:8002 uvicorn app.main:app --host 0.0.0.0 --port 8000

On PowerShell:

    $env:METADATA_SERVICE_URL = "http://127.0.0.1:8001"
    $env:MODEL_FINGERPRINT_SERVICE_URL = "http://127.0.0.1:8002"

## Tests

For the Model Fingerprinting service:

    cd backend/services/model-fingerprint
    python -m pip install -r requirements.txt
    pytest -q

For the Gateway, run its pytest suite from backend/api-gateway after installing requirements.txt. Tests have been authored but were not executed through the GitHub editing session; run both suites and a Docker Compose smoke test before merging.

## Production considerations

The SQLite store and local volume are a development baseline. Before public deployment, add authentication/authorization, rate limiting, malware scanning, object-storage lifecycle policies, encryption/key management, operational monitoring, and a reviewed retention policy. Kafka orchestration, PostgreSQL application persistence, and C2PA verification require dedicated implementations and tests.
