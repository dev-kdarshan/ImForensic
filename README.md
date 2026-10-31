# ImForensic

ImForensic is a modular image-forensics project for examining metadata, provenance indicators, and pixel-level evidence.

## Implemented engines

- **Metadata & Provenance:** extracts dimensions, format, EXIF and selected embedded metadata/provenance signals.
- **Model Fingerprinting:** extracts deterministic descriptive image features; does not attribute a generator/model.
- **Pixel Forensics (baseline):** inspects JPEG quantization tables and reports bounded high-pass residual and edge-response statistics. It deliberately returns inconclusive rather than declaring tampering.

The Pixel Forensics service is independently available on port 8003 in Docker Compose. It is not yet connected to the Gateway upload workflow; engine orchestration will be integrated after the planned engines are developed.

## Pixel Forensics

See [docs/pixel-forensics.md](docs/pixel-forensics.md) for method rationale, API, coordinate conventions, limitations, dataset/benchmark plan, and reproduction commands.

Run only this service:

    docker compose -f infrastructure/docker-compose.yml up --build pixel-forensics

API: http://localhost:8003/docs

Run its tests:

    cd backend/services/pixel-forensics
    python -m pip install -r requirements.txt
    pytest -q

Tests and benchmarks must be executed in the target environment before claiming a verified pass or publishing performance figures.

## Current architecture and remaining work

The Gateway currently calls Metadata & Provenance and Model Fingerprinting synchronously. Pixel Forensics is an independent service. Kafka orchestration, PostgreSQL application persistence, the remaining engines, evidence correlation, and end-to-end asynchronous reporting remain future work.

Production deployment still requires authentication/authorization, rate limiting, malware scanning, secure object storage, encryption/key management, monitoring, and a reviewed retention policy.
