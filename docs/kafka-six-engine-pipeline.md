# Kafka six-engine execution pipeline

## Implemented flow

Browser uploads an image to the API Gateway. The Gateway validates and hashes it, stores it under a UUID-derived object name, records a queued analysis, and submits a storage-reference-only job to the Orchestrator.

The Orchestrator publishes an analysis job and fans it out into six engine tasks. Six independently configured Kafka consumer groups each listen to the task stream and process only their assigned engine. Each worker fetches the image through the authenticated Gateway internal endpoint, verifies the SHA-256 digest, calls the existing HTTP analysis endpoint for its engine, normalizes the response, and publishes an engine result.

The result collector durably deduplicates results by analysis ID and engine, updates the Gateway record as results arrive, and invokes Evidence Correlation after all expected engines have terminal results. The frontend polls the Gateway and displays per-engine progress and the correlated response.

## Security and storage

Kafka messages carry identifiers, schema version, engine name, task ID, idempotency key, SHA-256 and opaque storage reference only. Image bytes travel over the authenticated internal HTTP endpoint to the selected engine. The Gateway resolves storage references from its database. Workers cannot supply arbitrary filesystem paths. The worker verifies the stored bytes against the upload SHA-256 before sending them to an engine.

The same non-empty IMFORENSIC_INTERNAL_TOKEN must be configured for the Gateway, all six engine workers, and result collector. Compose has a local-development fallback only. Replace it with a managed secret before any shared or production deployment. The current Gateway uses local SQLite and local disk storage; production object storage, encryption, retention/deletion, token rotation, and authorization controls remain deployment work.

## Delivery semantics

Kafka processing is at-least-once, not exactly-once. Deterministic task IDs, a unique result key on (analysis_id, engine), and Gateway engine-keyed result maps make replay idempotent at the result-record level. Workers retry transient HTTP/network failures up to three attempts. A terminal engine failure is published as a failed result so other engines can finish and correlation can report the failure. Collector offsets are committed only after persistence and callback delivery. Replayed callbacks can occur after a crash and must remain idempotent.

This does not provide a distributed transaction across Kafka, SQLite, HTTP services, and the correlation API. Topic retention, dead-letter operations for malformed engine results, monitoring, and production database reliability remain follow-up work.

## API behavior

Upload returns HTTP 202 with an analysis ID, queued status, expected engine list, and polling URL. Poll GET /api/v1/analyses/{analysis_id}. Status progresses through queued and processing to completed or partial. The correlation object appears after all six expected engine results are collected. Completed means all configured engines returned a completed execution status; it is not an authenticity or manipulation verdict.

AI Content Detection may return partial or failed if its DDA checkpoint is not installed/configured. A Kafka connection does not add missing model weights or unsupported detector capability. Each engine's raw output and scientific limitations remain preserved.

## Run locally

Set a strong local secret before starting Docker Compose. For PowerShell:

    $env:IMFORENSIC_INTERNAL_TOKEN = "replace-with-a-long-random-local-secret"
    docker compose -f infrastructure/docker-compose.yml config
    docker compose -f infrastructure/docker-compose.yml up --build

Run the focused tests:

    python -m pip install -r backend/orchestrator/requirements.txt -r backend/api-gateway/requirements.txt -r backend/evidence-correlation/requirements.txt pytest
    $env:PYTHONPATH = "backend;backend/orchestrator;backend/evidence-correlation;backend/api-gateway"
    pytest -q backend/shared/tests backend/orchestrator/tests backend/api-gateway/tests

Docker/Kafka end-to-end execution and live engine compatibility must be run locally before declaring the full integration operational. Do not claim tests or runtime validation succeeded until their output is observed.
