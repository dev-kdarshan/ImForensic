# ImForensic

ImForensic is a modular image-forensics project for examining metadata, provenance indicators, and other digital-image evidence.

## Implemented vertical slice

- React/Vite upload interface connected to the API Gateway.
- FastAPI Gateway validates JPEG, PNG, and WebP uploads, computes SHA-256, stores files privately, and persists analysis records in SQLite.
- Metadata & Provenance service extracts image dimensions, format, mode, EXIF, selected embedded metadata, software/XMP signals, and interpretation limitations.
- Gateway-to-engine connectivity uses configurable service DNS and sends image bytes over HTTP. The engine does not receive caller-controlled filesystem paths.
- Docker Compose starts the Gateway and Metadata service alongside Kafka, PostgreSQL, and Redis infrastructure.

The other forensic engines, Kafka orchestration, evidence correlation, C2PA signature verification, and AI-generation classification are not yet implemented. Missing metadata does not prove that an image is AI-generated or manipulated.

## Run with Docker

From the repository root:

    docker compose -f infrastructure/docker-compose.yml up --build

- API Gateway: http://localhost:8000 (API docs at /docs)
- Metadata engine: http://localhost:8001/docs
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

Start the Gateway in another terminal:

    cd backend/api-gateway
    python -m pip install -r requirements.txt
    METADATA_SERVICE_URL=http://127.0.0.1:8001 uvicorn app.main:app --host 0.0.0.0 --port 8000

On PowerShell, set the variable with $env:METADATA_SERVICE_URL = "http://127.0.0.1:8001".

## Tests

Install the relevant service requirements and run pytest from that service directory. Current tests cover metadata extraction, invalid uploads, service health, and persistence of partial results.

## Production considerations

The SQLite store and local volume are a development baseline. Before public deployment, add authentication/authorization, rate limiting, malware scanning, object-storage lifecycle policies, encryption/key management, operational monitoring, and a reviewed retention policy. C2PA verification and the remaining engines require dedicated implementations and test datasets.
