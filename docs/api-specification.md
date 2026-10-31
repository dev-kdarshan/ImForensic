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
- Returns HTTP 201 with analysis_id, status, SHA-256, file metadata, and the Metadata & Provenance result when available.

## Retrieve an analysis
- GET /api/v1/analyses/{analysis_id}
- Returns the persisted analysis record or HTTP 404.

## Metadata & Provenance service
- GET /health
- POST /analyze with multipart field file.
- The service accepts image bytes, not caller-supplied filesystem paths.

## Status values
- completed: Metadata & Provenance completed successfully.
- partial: The image was stored and hashed, but the metadata service did not return a valid result.
- failed: Reserved for terminal failures before a result can be persisted.

The current implementation performs metadata analysis in the upload request. Kafka-based asynchronous orchestration, SSE progress, and durable multi-engine aggregation remain future work.
