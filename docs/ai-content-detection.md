# AI Content Detection Engine — audit and implementation plan

**Current engine version:** 0.1.0 (service boundary only)  
**Current model state:** no detector configured; no model weights downloaded or committed  
**API port:** 8004  
**Current result:** `status=partial`, `findings.outcome=inconclusive`

## 1. Repository audit

Audited branch: `feature/pixel-forensics-baseline`.

| Area | Observed state |
|---|---|
| `app/analyzer.py` | Placeholder; no model loading or inference |
| `app/main.py` | Placeholder that prints a message |
| `app/kafka_consumer.py` | Placeholder; no Kafka consumer |
| `app/models/` | Only `.gitkeep`; no model artifacts |
| Tests | One placeholder test |
| Requirements | `confluent-kafka`, `pydantic`; no inference stack |
| Dockerfile | Runs the placeholder Python module; no HTTP API |
| Compose | No AI Content Detection service |
| Gateway | Calls Metadata & Provenance and Model Fingerprinting only |
| Orchestrator | Scaffold; not connected to this engine |
| Shared contract | `backend/shared/schemas/engine_result.py`: analysis_id, engine, status (completed/partial/failed), findings, warnings, model_version |
| Data/evaluation | No AI detector dataset, labels, model card, benchmark output, or evaluation script found in this engine directory |

The presence of a `models/` directory did not indicate a usable model: it contains only a placeholder file.

## 2. Initial task definition

The first evaluated task will be **whole-image binary screening of fully AI-generated images versus real photographs**.

In scope for the first detector evaluation:
- Fully AI-generated image vs real photograph.
- A documented closed list of generator families in the benchmark, with generator-disjoint holdouts.
- An explicit unknown-generator / out-of-distribution evaluation slice.
- Robustness tests for JPEG recompression, resizing, cropping, screenshots, and color changes.

Not in scope for the first classifier:
- Localizing AI-edited regions.
- Separating partially AI-edited images from fully generated images.
- Identifying the exact generator or model.
- Making authenticity or provenance determinations.
- Treating AI-modified photos as either class without a separately curated label policy.

Images with uncertain provenance, substantial mixed editing, or unsupported content should be reported as inconclusive/unsupported by the eventual inference layer, not forced into a confident binary decision.

## 3. Candidate model comparison

This is a shortlist for controlled evaluation, not a production model approval.

| Candidate | Evidence and architecture | License / artifact / operational considerations | Decision |
|---|---|---|---|
| **DDA — Dual Data Alignment (NeurIPS 2025 Spotlight)** | Official implementation and checkpoint; DINOv2 ViT-L/14 with LoRA; official authors report evaluations across 11 benchmarks and recommend broader multi-benchmark reporting | Official GitHub code is Apache-2.0; Hugging Face model card reports Apache-2.0; checkpoint is 1.26 GB (SHA-256: `b27a31d39374803ddeff02bfabb2be76e190b04300490cddfafb24f683f37e3e`). Official inference example assumes CUDA and loads a DINOv2 backbone through torch.hub. The checkpoint is a PyTorch pickle-based `.pth`; use safe weights-only loading if compatible, pin source revisions, verify digest, and never use unrestricted pickle loading on untrusted artifacts. Exact runtime/memory and CPU support are not yet measured. | **First candidate to evaluate**, not yet approved for deployment. Requires GPU/CPU feasibility test, secure loader review, pinned DINOv2 artifact, preprocessing reproduction, and independent benchmark. |
| **UnivFD (CVPR 2023)** | CLIP ViT-L/14 image features plus a linear fake/real head; useful simpler reference candidate | Official source repository declares MIT. The head checkpoint and CLIP backbone are separate artifacts; their hashes, provenance and redistribution terms must be pinned. Cross-generator performance can degrade on newer distributions. | Secondary baseline/comparison candidate. |
| **AIDE (ICLR 2025)** | Hybrid semantic and low-/high-frequency patch evidence; paper evaluates failure of existing detectors on challenging Chameleon images | Official code repository declares MIT; requirements pin an older stack including torch 1.11.0 and torchvision 0.12.0. Chameleon dataset license explicitly prohibits commercial use. Model checkpoint terms and compatibility need separate review. | Research comparison only; do not use Chameleon in commercial evaluation. |

### Candidate decision

Start with a **DDA inference feasibility and reproduction spike**, then compare against UnivFD on the same curated validation protocol. Do not ensemble models unless the independent validation set demonstrates a measurable improvement at an acceptable false-positive rate. AIDE is useful as a research comparator, but its old dependencies and Chameleon dataset restriction make it a less convenient first production candidate.

Published numbers in candidate papers/model cards are not ImForensic measurements. No candidate has been benchmarked in this repository.

## 4. Dataset and licensing review

No dataset or label manifest is currently present in the AI Content Detection directory.

Proposed evaluation sources:
- **GenImage:** large multi-generator benchmark; official repository describes over one million real/generated image pairs and includes multiple GAN/diffusion families. The repository points to third-party image sources; a dataset download link is not by itself a redistribution or commercial-use license. Audit individual source terms before use.
- **DDA training/evaluation sources:** official project lists GenImage, DRCT-2M, Synthbuster, RAISE-1k, ForenSynths, AIGCDetectionBenchmark, Chameleon, SynthwildX, WildRF, Bfree-Online, DDA-COCO and EvalGEN. Each source needs a separate license/provenance record.
- **Chameleon:** authors state academic research only and prohibit commercial use. Exclude from commercial training/evaluation unless written permission changes those terms.
- **DDA training set:** large hosted dataset; verify underlying image/source rights independently. Model card licensing does not automatically grant rights to every source image in a training dataset.

No dataset has been downloaded. Do not store source images or model weights in ordinary Git history.

## 5. Benchmark protocol

Build a manifest with one row per image and these required fields:
- stable image ID and SHA-256;
- label: `real`, `ai_generated`, `ai_edited`, `uncertain`, or `out_of_scope`;
- source dataset and source license;
- generator family/version for generated images;
- capture/source class for real images;
- transformation history;
- split assignment and provenance record.

Split requirements:
- Source-disjoint train/validation/test where feasible.
- Generator-disjoint holdout for unseen-generator testing.
- Exact and perceptual near-duplicate checks across splits.
- Class-balance and source-balance reports.
- Keep calibration separate from final test.
- Reserve an untouched external/wild evaluation set.

Transformation matrix:
- Original image.
- JPEG recompression at multiple quality settings.
- Resize/upscale/downscale with recorded interpolation.
- Crop and aspect-ratio changes.
- Screenshot / screen recapture.
- Color, contrast, saturation, and mild sharpening/denoising changes.

Metrics:
- Precision, recall, F1, confusion matrix.
- False-positive rate and specificity at a frozen operating threshold.
- ROC-AUC and PR-AUC where appropriate.
- Calibration metrics only after a separate calibration procedure.
- Results grouped by source, generator, and transformation.
- Runtime, peak RAM/VRAM, throughput, cold-start and warm inference.

Do not select the decision threshold on the final test split. Report trade-offs between false positives and false negatives. Establish numeric acceptance criteria only after the baseline is measured.

The evaluation harness in `evaluation/evaluate_predictions.py` consumes predictions, requires a frozen threshold, reports classification metrics and grouped performance, and rejects exact SHA-256 duplicates across different splits. It does not detect perceptual near-duplicates.

## 6. API and result semantics

Endpoints:
- `GET /health`: liveness.
- `GET /ready`: returns HTTP 503 until a model is configured and validated.
- `POST /analyze`: multipart field `file`, optional UUID `analysis_id`.

Current service behavior is intentionally `partial` / `inconclusive` with reason `MODEL_NOT_CONFIGURED`. No score or class is emitted.

Future detector result must include:
- detector name/version and artifact revision/hash;
- input and exact preprocessing version;
- raw score plus explicit direction/meaning;
- decision threshold and threshold-selection dataset;
- calibrated probability only after calibration testing;
- inconclusive/unsupported state and reason;
- model runtime, device, and processing time;
- warnings and limitations.

A raw sigmoid/logit/model confidence is not automatically a calibrated probability.

## 7. Production and security gates

Before enabling inference:
1. Pin source repository commit and artifact revision.
2. Verify checkpoint SHA-256 at startup.
3. Review model and dataset licenses separately.
4. Load tensor weights safely; do not allow arbitrary pickle execution.
5. Pin torch/torchvision and image-decoder versions; reproduce official preprocessing.
6. Load once per process, bound concurrency and input size, and configure timeouts.
7. Benchmark CPU and target GPU memory/runtime; avoid requiring a GPU until measurements justify it.
8. Log model/artifact/preprocessing versions and metrics, never image bytes.
9. Add a controlled artifact cache/volume; keep weights out of Git.
10. Integrate with Gateway only after the detector returns a verified structured result.

Kafka is intentionally not implemented in this engine stage. The eventual message should carry analysis/job identifiers and controlled storage references, never raw image bytes.

## 8. Current limitations and next milestones

- No AI detection model is loaded.
- No benchmark has been run.
- No accuracy or runtime claim is made.
- No CPU/GPU compatibility has been measured.
- No training or dataset license has been approved for a commercial use case.
- The service is not connected to Gateway or Kafka.

Next: perform the DDA artifact/runtime feasibility spike, implement the pinned model adapter only after it passes security and compatibility review, then run the benchmark protocol and compare with UnivFD.
