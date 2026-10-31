# Pixel Forensics Engine

## Scope and scientific position

Version 0.1.0 is an explainable signal-processing baseline. It measures compression metadata and simple pixel-domain residual/edge statistics. It does not decide whether an image is authentic or manipulated, and does not localize tampering. All current findings are descriptive and the overall outcome is `inconclusive`.

## Methods implemented

### JPEG quantization-table inspection
For JPEG files, the engine reports decoder-exposed quantization tables in their original zig-zag ordering, including coefficient count, minimum, maximum, and mean. This can document compression characteristics. Quantization tables can be replaced by recompression and are not unique to an encoder, editing application, or manipulation event. For PNG and WebP, this method is marked not applicable.

### High-pass residual summary
The engine converts a bounded sample to grayscale, applies Gaussian blur with radius 1.0, and measures the absolute difference between the sample and its smoothed version. It reports global mean/standard deviation and per-tile mean/standard deviation on up to a 4x4 grid. The tile bounds are mapped back to original decoded-image pixel coordinates (origin top-left; right/bottom exclusive). These are not sensor-noise estimates, calibrated anomaly scores, or tamper probabilities.

### Edge-response summary
Pillow FIND_EDGES provides a simple edge-response proxy. The engine reports mean and standard deviation. This is not a validated resampling detector.

## Deliberately deferred methods

- Double-JPEG detection: requires a validated estimator and controlled recompression benchmark; quantization-table inspection alone is insufficient.
- Resampling periodicity detection: requires validation across resize kernels, scale factors, crops, and recompression.
- Copy-move detection: requires a defensible block/feature matching method, duplicate suppression, and localization benchmark.
- Inpainting/compositing classification: deferred until labelled data and a defined task exist.
- Learned detection: no model or GPU dependency is introduced without a suitable dataset and cross-source evaluation.

## API

- `GET /health`: process liveness.
- `GET /ready`: service readiness and execution mode.
- `POST /analyze`: multipart field `file`, optional UUID `analysis_id`.

Accepted inputs: JPEG, PNG, WebP; maximum 20 MB and 40 megapixels. API runs on port 8003. The response follows the existing shared EngineResult core fields (`analysis_id`, `engine`, `status`, `findings`, `warnings`, `model_version`) and adds version, method configuration, evidence, timing, resource bounds, and limitations. No Kafka messages contain image bytes.

## Safety and resources

The service validates format, byte size, dimensions, and decoded image integrity. Pixel processing is bounded to a 512-pixel maximum sample side; no GPU or additional numerical package is required. Execution time is measured per request. Configure container CPU/memory limits after benchmarking representative images; no numeric performance claims are made here.

## Dataset and benchmark plan

Build a versioned dataset with source-disjoint genuine and manipulated images, manipulation masks where available, and difficult benign negatives. Include copy-move, splicing/compositing, inpainting, and benign transformations (JPEG recompression at multiple qualities, resizing with several kernels, cropping, color correction, denoising, sharpening, and format conversion). Record provenance, license, image dimensions, manipulation operation, mask coordinates, and train/validation/test split.

For a future detector, report image-level precision, recall, F1, false-positive rate, and (where masks exist) pixel precision/recall and IoU. Report results by source and transformation, plus runtime and peak memory. Establish numeric acceptance targets only after dataset inspection and a baseline measurement.

## Reproduction

From this directory:

```bash
python -m pip install -r requirements.txt
pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8003
```

Docker Compose from repository root:

```bash
docker compose -f infrastructure/docker-compose.yml up --build pixel-forensics
```

## Limitations

No accuracy, precision, recall, F1, localization, or runtime benchmark results are claimed until commands are executed on a documented dataset and target hardware. EXIF orientation is not applied; reported coordinates use the decoded raster dimensions.
