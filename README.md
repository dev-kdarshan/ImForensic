# ImForensic

ImForensic is a modular image-forensics project for examining metadata, provenance indicators, and digital-image evidence.

## Implemented engines

- **Metadata & Provenance:** extracts dimensions, format, EXIF and selected embedded metadata/provenance signals.
- **Model Fingerprinting:** extracts deterministic descriptive image features; does not attribute a generator/model.
- **Pixel Forensics (baseline):** inspects JPEG quantization tables and reports bounded high-pass residual and edge-response statistics. It deliberately returns inconclusive rather than declaring tampering.
- **AI Content Detection (service boundary):** validates image input and exposes the shared engine-result shape. No AI detector is configured yet, so results are partial/inconclusive until a model is selected, secured and benchmarked.
- **Visual Consistency (descriptive baseline):** reports regional luminance, colour and edge-response measurements with cautious within-image outlier flags. It does not infer lighting physics, shadows, perspective, objects, or manipulation.

See [docs/ai-content-detection.md](docs/ai-content-detection.md) for the repository audit, task definition, model comparison, data/licensing review, evaluation plan, and implementation gates.

## Run with Docker

From the repository root:

    docker compose -f infrastructure/docker-compose.yml up --build

- API Gateway: http://localhost:8000 (API docs at /docs)
- Metadata engine: http://localhost:8001/docs
- Model Fingerprinting engine: http://localhost:8002/docs
- Pixel Forensics engine: http://localhost:8003/docs
- AI Content Detection engine: http://localhost:8004/docs
- Visual Consistency engine: http://localhost:8006/docs

The AI Content Detection service is not yet connected to the Gateway upload workflow. Its `/ready` endpoint returns HTTP 503 until a vetted model artifact is configured.

Run the frontend separately:

    cd frontend
    npm install
    npm run dev

## Run AI Content Detection tests

    cd backend/services/ai-content-detection
    python -m pip install -r requirements.txt
    pytest -q

## Run Visual Consistency tests

    cd backend/services/visual-consistency
    python -m pip install -r requirements.txt
    pytest -q

See [docs/visual-consistency.md](docs/visual-consistency.md) for the task scope, measurement semantics, dataset protocol, and limitations.

## Evaluate a detector

The evaluation harness consumes a CSV of predictions and applies a frozen threshold:

    python backend/services/ai-content-detection/evaluation/evaluate_predictions.py predictions.csv --split test --threshold 0.5 --score-semantics raw_score --output metrics.json

Do not treat raw model scores as probabilities. See the engine documentation for required dataset provenance and split controls.

## Current architecture and remaining work

The Gateway currently calls Metadata & Provenance and Model Fingerprinting synchronously. Pixel Forensics and AI Content Detection are independent services. Kafka orchestration, PostgreSQL application persistence, the remaining engines, evidence correlation, and end-to-end asynchronous reporting remain future work.

Production deployment still requires authentication/authorization, rate limiting, malware scanning, secure object storage, encryption/key management, monitoring, and a reviewed retention policy.
