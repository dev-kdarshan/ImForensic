# Watermark Detection Engine

Standalone ImForensic service, port **8005**. The first implementation deliberately supports a narrow, auditable scope.

## Current capability

- Reads C2PA Content Credentials with the official `c2pa-python` reader (read-only).
- Reports manifest discovery separately from SDK validation findings and trust/identity assessment.
- Scans metadata key names for watermark/C2PA-related candidate markers. This is a weak signal only.
- Validates JPEG, PNG and WebP input before analysis, with 20 MB and 40-megapixel limits.
- Returns explicit partial/inconclusive outcomes when the C2PA reader is unavailable or fails.

**C2PA is provenance credentials, not a watermark algorithm.** A C2PA manifest may contain origin and editing assertions. Its presence does not prove the claims are true, and signature validity does not automatically establish signer identity trust.

## Not implemented

- OCR or logo/template matching for visible marks.
- Any generic invisible watermark detector.
- SynthID or other proprietary platform-specific scheme.
- Scheme-specific keyed decoding, payload attribution, or ownership verification.
- C2PA trust-anchor configuration. SDK validation details are reported, but trusted identity is not asserted.

The engine must not claim a watermark is absent because it did not find a supported signal. Metadata key candidates can be false positives. No detector score, accuracy, precision, recall, or robustness claim is made.

## API

- `GET /health`: process liveness.
- `GET /ready`: reports SDK availability and enabled detector inventory.
- `POST /analyze`: multipart `file`, optional UUID `analysis_id`.

The response separates `watermark_evidence`, `content_credentials`, and `decoding`. The top-level outcome is one of `detected`, `potential_candidate`, `not_detected`, or `inconclusive`. `not_detected` means only that the configured C2PA reader did not find a manifest and no metadata candidate was surfaced; invisible and visible watermark algorithms remain unsupported.

## Run locally

```bash
cd backend/services/watermark-detection
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8005
pytest -q
```

## Docker

From `infrastructure/`, use the Compose service `watermark-detection`. The C2PA Python binding includes a native library; verify wheel/platform compatibility in the target build environment before deployment.

## License and supply-chain notes

The C2PA Python binding is published by the Content Authenticity Initiative and its upstream repository declares Apache-2.0 and MIT licensing. The dependency is pinned to `c2pa-python==0.38.3`; its native wheel size and platform availability should be checked for each target architecture. No model weights, external detector package, private key, or signing operation is included.

## Evaluation still required

Build a legally sourced corpus of C2PA-present, C2PA-absent, invalid-manifest, and transformed assets. Include JPEG recompression, resize, crop and format conversion. Test each supported format and target CPU architecture. Report parser success, false positives, false negatives, runtime and memory separately. This PR does not contain an independently validated benchmark corpus.
