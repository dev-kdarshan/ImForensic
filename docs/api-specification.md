# API specification

Base URL: http://localhost:8000

## Health
- GET /health — API Gateway liveness.

## Create an analysis
- POST /api/v1/analyses
- Content type: multipart/form-data
- Field: file
- Accepted media types: JPEG, PNG, WebP.
- Maximum upload: 20 MB by default (MAX_UPLOAD_MB).
- Returns HTTP 201 with analysis_id, status, SHA-256, file metadata, per-engine status, and available engine results.
- The Gateway sends the same uploaded bytes to Metadata & Provenance and Model Fingerprinting over internal HTTP. It verifies each engine's SHA-256 before accepting that engine's result.

## Retrieve an analysis
- GET /api/v1/analyses/{analysis_id}
- Returns the persisted analysis record, including engine_results, or HTTP 404.

## Engine services
- Metadata & Provenance: GET /health; POST /analyze with multipart field file.
- Model Fingerprinting: GET /health; GET /ready; POST /analyze with multipart field file and optional analysis_id.
- Engine result statuses are recorded independently. One engine failure does not discard a verified result from another engine.

## Analysis status values
- completed: all currently connected engines returned hash-verified results.
- partial: at least one connected engine failed or returned an invalid/hash-mismatched response.

The upload workflow currently calls the two engines synchronously. Kafka-based asynchronous orchestration, SSE progress, and durable multi-engine aggregation remain future work.
