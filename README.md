# ImForensic

ImForensic is a modular image-forensics project for examining metadata, provenance indicators, and other digital-image evidence.

## Implemented vertical slice

- React/Vite upload interface connected to the API Gateway.
- FastAPI Gateway validates JPEG, PNG, and WebP uploads, computes SHA-256, stores files privately, and persists analysis records in SQLite.
- Metadata & Provenance service extracts image dimensions, format, mode, EXIF, selected embedded metadata, software/XMP signals, and interpretation limitations.
- Gateway-to-engine connectivity uses configurable service DNS and sends image bytes over HTTP. The engine does not receive caller-controlled filesystem paths.
- Model Fingerprinting service now provides a deterministic descriptive feature-extraction baseline through a standalone HTTP API. It reports an inconclusive attribution outcome and does not claim generator identification.
- Docker Compose includes the Gateway, Metadata & Provenance, Model Fingerprinting, Kafka, PostgreSQL, and Redis services.

The Model Fingerprinting baseline currently extracts channel statistics/histograms/entropy, grayscale entropy/histogram, a simple edge-response statistic, and coarse spatial luminance measurements. It does not contain a trained classifier, reference dataset, candidate ranking, or calibrated probabilities. See [Model Fingerprinting documentation](docs/model-fingerprinting.md).

The remaining four forensic engines, Kafka orchestration, evidence correlation, SSE progress, C2PA signature verification, and AI-generation classification are not yet implemented. The current Gateway upload workflow still invokes Metadata & Provenance only; Model Fingerprinting is exposed as a separate service and has not yet been wired into the Gateway workflow. Missing metadata does not prove that an image is AI-generated or manipulated.

## Run with Docker

From the repository root:

    docker compose -f infrastructure/docker-compose.yml up --build

- API Gateway: http://localhost:8000 (API docs at /docs)
- Metadata engine: http://localhost:8001/docs
- Model Fingerprinting engine: http://localhost:8002/docs
- Gateway health: http://localhost:8000/health

Run the frontend separately:

    cd frontend
    npm install
    npm run dev

Set VITE_API_BASE_URL=http://localhost:8000 in frontend/.env if required.

## Run backend services locally

Start Metadata:

    cd backend/services/metadata-provenance
    python -m pip install -r requirements.txt
    uvicorn app.main:app --host 0.0.0.0 --port 8001

Start Model Fingerprinting in another terminal:

    cd backend/services/model-fingerprint
    python -m pip install -r requirements.txt
    uvicorn app.main:app --host 0.0.0.0 --port 8002

Start the Gateway in another terminal:

    cd backend/api-gateway
    python -m pip install -r requirements.txt
    METADATA_SERVICE_URL=http://127.0.0.1:8001 uvicorn app.main:app --host 0.0.0.0 --port 8000

On PowerShell, set the variable with $env:METADATA_SERVICE_URL = "http://127.0.0.1:8001".

## Tests

For the Model Fingerprinting service:

    cd backend/services/model-fingerprint
    python -m pip install -r requirements.txt
    pytest -q

The tests are authored but have not yet been executed in this environment. Existing Metadata & Gateway tests also need to be run before merging PR #1.

## Production considerations

The SQLite store and local volume are a development baseline. Before public deployment, add authentication/authorization, rate limiting, malware scanning, object-storage lifecycle policies, encryption/key management, operational monitoring, and a reviewed retention policy. Kafka job-reference integration, PostgreSQL application persistence, and C2PA verification require dedicated implementations and tests.
