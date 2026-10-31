# Shared ImForensic Engine Integration Contract

## Contract version

The shared request/result envelope and Kafka payloads in this change use schema version **1.0.0**. Engine-specific findings remain owned by each engine and are preserved in raw_result.

## Request contract

AnalysisRequest requires a UUID analysis_id, a SHA-256 digest, a non-empty list of supported engine names, and an opaque image_ref. References must use storage://, s3://, gs://, or HTTPS. Local filesystem paths and traversal segments are rejected. Kafka messages carry references and identifiers only; never image bytes.

## Result contract

EngineResult adds schema version, analysis and engine identity, engine version, status (completed, partial, failed), stable finding IDs, source-engine/path attribution, evidence observations, warnings, limitations, score semantics, safe error structure, and processing duration. The compatibility normalizer wraps legacy engine payloads without discarding or rewriting their raw findings. Stable finding IDs are SHA-256-derived identifiers over analysis ID, engine name, and source path.

## Evidence separation and correlation

Each engine remains responsible for its own observations. Correlation preserves the normalized source results and reports missing, failed, partial, and duplicate engine results. Conflicts are only raised for observations that explicitly provide the same comparison_key; the service does not guess semantic equivalence. Scores are never averaged, and correlated findings are not assumed independent.

## Distributed processing

The Orchestrator HTTP API publishes analysis-jobs; the Kafka worker fans each valid request into one engine-tasks message per requested engine. Messages use analysis_id and deterministic task_id keys and contain an opaque image reference, digest, schema version and idempotency key. The worker uses manual offset commits, bounded producer retries, and an invalid-job dead-letter topic. Delivery is **at least once**, not exactly once. A consumer must persist/deduplicate task_id before side effects. Engine-task consumers and engine-result ingestion are not implemented in this increment.

## Storage and privacy

The Gateway existing storage abstraction uses UUID-derived filenames under its configured upload directory and exposes deletion by analysis ID. Do not pass caller-controlled paths. The Orchestrator and Kafka receive only opaque references. Current Gateway storage has no configured retention scheduler or authenticated per-object access layer; deployments must define retention, deletion workflow, encryption, and authorization before production. Avoid logging image bytes, secrets, or raw sensitive metadata.

## Affected services and migration

- All six engines: legacy HTTP response bodies are not rewritten by this change. Consumers should normalize them with the shared compatibility helper.
- Gateway: existing synchronous Metadata/Model Fingerprint calls remain unchanged; asynchronous submission is exposed by Orchestrator separately.
- Orchestrator: new /jobs API and Kafka fan-out worker.
- Evidence Correlation: new /correlate API.
- Infrastructure: Docker Compose fixes the committed merge-conflict markers, adds Orchestrator/Correlation services, and separates internal Kafka kafka:9092 from host access localhost:9094.

Before migrating engine HTTP responses to the canonical envelope, update Gateway response parsing, frontend rendering, persisted records, and each engine API tests together. This change deliberately avoids a breaking all-engine migration.

## Validation and status

The schema, normalizer, correlation logic, and request validation have unit tests. Docker/Kafka end-to-end execution and the six-engine compatibility matrix remain unverified until run in the target environment. No benchmark or forensic accuracy claim is made by this contract layer.

## Local commands

    python -m pip install -r backend/orchestrator/requirements.txt -r backend/evidence-correlation/requirements.txt
    PYTHONPATH=backend pytest -q backend/shared/tests backend/orchestrator/tests backend/evidence-correlation/tests
    docker compose -f infrastructure/docker-compose.yml config
    docker compose -f infrastructure/docker-compose.yml up --build
