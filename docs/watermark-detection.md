# Watermark & Content Credentials Engine

## 1. Repository audit

The pre-existing `backend/services/watermark-detection` directory contained a print-only `main.py`, an analyzer placeholder, a placeholder Kafka consumer, a dependency list containing only `confluent-kafka` and `pydantic`, a generic Python Dockerfile, and one test that asserted `True`. There was no watermark algorithm, C2PA parser, image validation, API, detector implementation, or meaningful test coverage.

The shared result contract in `backend/shared/schemas/engine_result.py` contains `analysis_id`, `engine`, `status` (`completed|partial|failed`), `findings`, `warnings`, and optional `model_version`. This service preserves those core fields and adds engine-specific evidence details inside `findings`; no shared interface was changed.

## 2. Supported scope in this draft

| Category | Current status | Evidence produced |
|---|---|---|
| Visible watermark | Unsupported | Explicitly reports no OCR/template/localizer is enabled |
| Invisible/robust watermark | Unsupported | No generic decoder or scheme-specific key |
| Platform-associated schemes | Unsupported | No SynthID or proprietary scheme claim |
| C2PA Content Credentials | Supported for manifest reading | C2PA manifest summary and SDK validation-status entries |
| Metadata markers | Candidate-only | Key names containing watermark/C2PA terms |

C2PA credentials are provenance information, not watermark pixels or an invisible watermark signal. Metadata marker matches are potential candidates only.

## 3. Detection, decoding, attribution and verification

- **Detection:** a supported reader finds a C2PA manifest, or a metadata key candidate is observed.
- **Decoding:** the C2PA reader parses a manifest store. No invisible watermark payload is decoded.
- **Attribution:** claim-generator strings are self-asserted manifest data, not independently proven authorship.
- **Verification:** SDK validation-status entries are surfaced. This draft does not configure trust anchors or assert signer identity trust.
- **Non-detection:** means only that this implementation did not surface supported evidence. It cannot establish that the image contains no watermark.

## 4. Method and dependency review

The C2PA Python binding is the official Python binding to the C2PA Rust implementation. Upstream usage documents stream-based reading through `Reader(mime_type, stream)` and `reader.json()`, with validation errors represented in the report's `validation_status`. The project declares MIT OR Apache-2.0. The dependency is pinned to `c2pa-python==0.38.3`.

Pillow is used only for safe image decoding, dimension checks, and metadata-key inspection. It is not used as a watermark detector. No OCR, learned model, proprietary SDK, external model weights, signing keys, or third-party detector is introduced.

## 5. API and security

- `GET /health`
- `GET /ready`
- `POST /analyze` multipart upload with optional UUID `analysis_id`
- JPEG, PNG and WebP only
- 20 MB input and 40-megapixel image limits
- In-memory streams; no temporary image files
- No key material or full arbitrary metadata values in ordinary responses/logs
- Native C2PA errors are not returned to clients
- Independent service on port 8005; no Gateway or Kafka integration in this engine-development milestone

## 6. Evaluation plan and outstanding validation

Create legally sourced fixtures for C2PA-present, C2PA-absent, malformed/truncated manifests, invalid signatures, and metadata-key hard negatives. Add transformed versions (recompression, resizing, crop and format conversion) where expected behavior is documented. Measure C2PA manifest read success, parser error classification, false-positive/negative rates, runtime and memory by format and platform.

Tests in this PR are authored but must be run in the repository environment. Also outstanding: Docker build, native wheel compatibility on x86-64 and ARM64, real signed fixture verification, C2PA trust-anchor policy, and a full benchmark. No measured accuracy or production readiness is claimed.
