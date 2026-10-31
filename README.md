# ImForensic

ImForensic is a modular image-forensics project for examining metadata, provenance indicators, and digital-image evidence.

## Implemented engines

- **Metadata & Provenance:** extracts dimensions, format, EXIF and selected embedded metadata/provenance signals.
- **Model Fingerprinting:** extracts deterministic descriptive image features; does not attribute a generator/model.
- **Pixel Forensics (baseline):** inspects JPEG quantization tables and reports bounded high-pass residual and edge-response statistics. It deliberately returns inconclusive rather than declaring tampering.
- **AI Content Detection (service boundary):** validates image input and exposes the shared engine-result shape. No AI detector is configured yet, so results are partial/inconclusive until a model is selected, secured and benchmarked.

See [docs/ai-content-detection.md](docs/ai-content-detection.md) for the repository audit, task definition, model comparison, data/licensing review, evaluation plan, and implementation gates.

## Run with Docker

From the repository root:

    docker compose -f infrastructure/docker-compose.yml up --build

- API Gateway: http://localhost:8000 (API docs at /docs)
- Metadata engine: http://localhost:8001/docs
- Model Fingerprinting engine: http://localhost:8002/docs
- Pixel Forensics engine: http://localhost:8003/docs
- AI Content Detection engine: http://localhost:8004/docs

The AI Content Detection service is not yet connected to the Gateway upload workflow. DDA inference is experimental and remains unready until a locally mounted checkpoint with the pinned SHA-256 is configured. See [DDA inference and benchmark guide](backend/services/ai-content-detection/docs/dda-and-benchmark.md).

Run the frontend separately:

    cd frontend
    npm install
    npm run dev

## Run AI Content Detection tests

    cd backend/services/ai-content-detection
    python -m pip install -r requirements.txt
    pytest -q

## Evaluate a detector

The evaluation harness consumes a CSV of predictions and applies a frozen threshold:

    python backend/services/ai-content-detection/evaluation/evaluate_predictions.py predictions.csv --split test --threshold 0.5 --score-semantics raw_score --output metrics.json

Do not treat raw model scores as probabilities. For DDA, install the optional pinned model dependencies separately and configure `DDA_CHECKPOINT_PATH` plus `DDA_CHECKPOINT_SHA256`; weights are not committed. See the DDA guide for inference and source-/generator-disjoint benchmarking.

## Current architecture and remaining work

The Gateway currently calls Metadata & Provenance and Model Fingerprinting synchronously. Pixel Forensics and AI Content Detection are independent services. Kafka orchestration, PostgreSQL application persistence, the remaining engines, evidence correlation, and end-to-end asynchronous reporting remain future work.

Production deployment still requires authentication/authorization, rate limiting, malware scanning, secure object storage, encryption/key management, monitoring, and a reviewed retention policy.
