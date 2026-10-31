# Visual Consistency Engine

## 1. Repository audit

Audited against the `feature/ai-content-detection-engine` base used for this PR. The prior Visual Consistency directory contained a print-only `main.py`, placeholder `analyzer.py` and Kafka consumer, a placeholder test, and empty model/analyzer directories. There was no HTTP API, usable model, inference code, or task-specific evaluation data. The shared result contract is `EngineResult(analysis_id, engine, status, findings, warnings, model_version)`; this service preserves those core fields and adds descriptive evidence.

The Pixel Forensics engine already reports JPEG quantization tables, grayscale high-pass residuals, and edge-response statistics. This engine does not duplicate those measurements as forensic conclusions. It measures regional luminance, saturation, RGB channel means, and edge-response variation as scene-level context.

## 2. Selected initial task

**Task:** bounded, within-image comparison of regional illumination proxies, colour distribution, and edge/texture response.

**Not in this baseline:** physical light-source direction, cast-shadow geometry, vanishing points, camera calibration, object detection/segmentation, occlusion reasoning, semantic/vision-language inference, or manipulation classification.

The implementation deliberately does not use a pretrained model. No candidate model has a defined task-specific benefit that justifies its licensing, artifact, runtime, and evaluation burden for these descriptive measurements.

## 3. Method comparison

| Candidate method | What it can measure | Key assumptions / failure modes | Decision |
|---|---|---|---|
| Regional grayscale luminance mean and standard deviation | Local brightness distribution and within-region spread | Scene depth, materials, exposure, vignetting, shadows, and natural illumination gradients change values | Implemented as descriptive measurements |
| Regional HSV saturation and RGB means | Regional colour distribution | White balance, colour grading, mixed materials, lighting spectra, and compression alter values | Implemented as descriptive measurements |
| Regional edge-response statistics | Coarse local edge/texture activity | Fine texture, blur, sharpening, resampling, and scene content affect response; not a physical texture classifier | Implemented as a simple proxy |
| MAD-based within-image comparison | Regions whose scalar measurements differ from the image's regional median | Small sample count and zero MAD; spatially structured scenes naturally create outliers; threshold is a heuristic | Implemented only as an uncalibrated descriptive flag |
| Shadow direction / light-source estimation | Potential physical relationships between shadows and illumination | Requires reliable shadow segmentation, geometry, material assumptions, and scene interpretation; multiple lights and indirect illumination complicate inference | Deferred |
| Perspective / vanishing-point analysis | Geometric line convergence under suitable scene assumptions | Requires line evidence and assumptions about planar/parallel structures; wide-angle lenses and intentional perspective complicate interpretation | Deferred |
| Object detection / segmentation / VLM | Candidate object boundaries and semantic relations | Model-specific domain shift, license, localization errors, and unsupported semantic reasoning | Deferred pending a task and benchmark |

### Measurement semantics

The engine downsamples the decoded RGB image to a maximum 512-pixel side using Pillow BILINEAR. It divides the sample into up to a 4x4 grid, with each tile at least 16 pixels on a side where possible. For each tile it measures grayscale luminance mean/stddev, HSV saturation mean, RGB channel means, and Pillow FIND_EDGES mean/stddev.

For luminance, saturation, and edge-response means, it computes a within-image robust standardized deviation:

`robust\_z = 0.67448975 \times (x - median(x)) / MAD(x)`

where MAD is the median absolute deviation across the image's regions. A threshold of absolute robust z >= 3.5 marks a *statistical outlier measurement*, not a suspicious region, manipulation, or forgery. If fewer than three regions exist or MAD is zero, no outlier is marked. The output includes source-raster coordinates; EXIF orientation is not applied.

## 4. Output and API

- `GET /health`: liveness.
- `GET /ready`: service readiness and descriptive execution mode.
- `POST /analyze`: multipart image field `file`, optional UUID `analysis_id`.

The response preserves the shared core EngineResult fields and adds `engine_version`, image digest/dimensions, method configuration, regional evidence, score semantics, warnings, limitations, processing time, and resource bounds. Overall outcome remains `inconclusive`; `manipulation_supported` is always false. No global manipulation score or calibrated probability is emitted.

Accepted formats: JPEG, PNG, WebP. Maximum input size: 20 MB. Maximum decoded image size: 40 megapixels. Sample side: 512 pixels. Port: 8006. No GPU or external model artifact is required.

## 5. Dataset and evaluation protocol

No dataset is bundled and no performance metric is claimed. A future task-specific benchmark should contain:

- Authentic images from multiple independent sources and capture devices.
- Known manipulated images with documented operations and, where available, expert-checked region masks.
- Difficult benign cases: strong natural lighting gradients, mixed illumination, reflective materials, hard shadows, patterned textures, depth-of-field blur, high-contrast scenes, and ordinary edits.
- For any future shadow task: annotations for shadow regions, candidate light-source direction/uncertainty, scene geometry assumptions, and expert agreement.
- For any future geometry task: line/vanishing-point annotations and explicit scene eligibility labels.

Record source, provenance, license, capture/processing history, manipulation operation, annotation method, and split membership. Split by source/subject and manipulation lineage to reduce leakage; do not place derivatives of the same source image across train and test. Keep a locked test set.

For a future region detector, report precision, recall, F1, false-positive rate, region localization IoU/precision-recall where masks exist, and expert agreement. Evaluate separately by scene type, source, image transformation, and manipulation family. Measure cold/warm latency, throughput, peak memory, and container/model size on named hardware. Set acceptance thresholds only after a measured baseline. Do not aggregate unrelated lighting, geometry, and semantic tasks into one accuracy figure.

## 6. Reliability and security

Input validation checks byte length, decoded format, dimensions, and image integrity before loading. Processing is bounded by a 512-pixel sample and a maximum 4x4 region grid. The API reads at most the configured limit plus one byte. No image bytes are logged. The service has no Kafka consumer in this phase; the previous Kafka file remains an explicit placeholder and image bytes are not placed on Kafka.

## 7. Deployment and reproduction

From this directory:

```bash
python -m pip install -r requirements.txt
pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8006
```

From repository root:

```bash
docker compose -f infrastructure/docker-compose.yml up --build visual-consistency
```

The Compose service exposes host port 8006 and has a health check against `/ready`. Configure CPU/memory limits only after measuring representative images; no resource benchmark is claimed.

## 8. Limitations and next research gates

- Regional differences are expected in ordinary photographs and are not evidence of tampering.
- The current edge response is not a validated texture descriptor.
- No physical lighting, shadow, perspective, object, or semantic consistency is inferred.
- No learned detector, training data, or calibration is present.
- The output is descriptive and inconclusive, not a forensic authenticity verdict.

Before adding shadow or geometry models, define an eligible-scene protocol, obtain licensed annotations, reproduce a baseline, evaluate false positives on difficult benign scenes, and document model/artifact licenses and resource costs.
