# Model Fingerprinting Engine

## 1. Current scientific scope

The first implementation is a **descriptive feature-extraction baseline**, not a generator classifier. It computes repeatable image statistics that can later be studied against labelled reference datasets.

Supported now:
- deterministic RGB channel means, standard deviations, 16-bin histograms and Shannon entropy;
- grayscale entropy and a 32-bin histogram;
- a simple edge-response statistic using Pillow's `FIND_EDGES`;
- luminance means over up to a 4x4 spatial tile grid;
- SHA-256, source dimensions, sampled dimensions and preprocessing metadata.

Not supported now:
- exact model or generator identification;
- candidate-generator ranking or similarity scores;
- calibrated probabilities or confidence;
- unknown-generator rejection learned from data;
- claims that any statistic is unique to AI-generated images.

The response therefore uses `findings.outcome = "inconclusive"`, `attribution_supported = false`, and an empty `candidate_scores` list. A successful feature extraction has `status = "completed"`; completed describes execution, not successful attribution.

## 2. Candidate-method assessment

| Candidate | Scientific rationale | Cost / dependencies | Main limitations and evaluation |
|---|---|---|---|
| Statistical and spatial features (implemented baseline) | Summarize channel distributions, entropy, edges and coarse spatial variation | Low; Pillow and CPU | Highly content- and transform-dependent; descriptive only until validated across controlled datasets |
| Frequency-domain features | Generator pipelines may leave spectral regularities | Low-to-medium; numerical FFT library such as NumPy | Resizing, JPEG and post-processing alter spectra; compare across controlled transformations and real-image sources |
| Residual/noise features | Demosaicing, denoising and synthesis pipelines can affect residual statistics | Medium; numerical/image-processing dependencies | Camera pipeline and compression confound signals; needs camera/source diversity |
| Learned embeddings | Encoders can represent higher-level image statistics | Medium-to-high; model framework and pretrained weights | Domain and training-data bias; licensing and model provenance review; embeddings are not inherently model fingerprints |
| Supervised classifier | Learns distinctions among explicitly labelled candidate sources | High; training pipeline and labelled dataset | Leakage, class imbalance and closed-set overconfidence; requires source-separated and open-set tests |
| Similarity against reference sets | Measures proximity to known examples or feature distributions | Medium; curated, indexed reference corpus | Similarity is not probability or proof; sensitive to reference coverage and duplicate leakage |
| Open-set/OOD detection | Can abstain when inputs differ from known training classes | Medium-to-high; validated classifier/embedding and calibration protocol | Unknown detection is difficult; evaluate false acceptance and false rejection on held-out generators |
| Ensembles | May combine complementary validated signals | High; multiple maintained models | Added complexity is unjustified unless independent evaluation demonstrates improvement |

No model family or pretrained weights were selected. The repository currently contains no verified fingerprint dataset or model artifact. This avoids silently introducing a large dependency, unreviewed licence, or unsupported model attribution.

## 3. Dataset and evaluation protocol

Before training a candidate classifier, create a versioned dataset manifest with:
- source/provider, collection date, provenance, licence and permitted use;
- real/generated label, generator family and exact model/version when known;
- prompt, seed, sampler, dimensions and generation settings where available;
- original-file SHA-256, perceptual/near-duplicate grouping and exclusion reason;
- transformation lineage (resize, JPEG quality, crop, screenshot, editing, format conversion).

Split by source and near-duplicate group, not by random image rows. Keep a final test set untouched during feature/model selection. Reserve one or more generator families entirely for open-set evaluation. Record class balance and use macro-F1 and per-class precision/recall; include confusion matrices, false-positive/false-negative rates, calibration metrics only for calibrated probabilities, and unknown-source rejection metrics. Repeat robustness tests over controlled transformations. Establish acceptance targets only after measuring a baseline and report confidence intervals where feasible.

No dataset is bundled or downloaded by this implementation. Dataset licences, labels and availability must be verified before use.

## 4. API

Run locally:

```powershell
cd backend/services/model-fingerprint
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Endpoints:
- `GET /health`: process health.
- `GET /ready`: readiness and active mode; currently no attribution model is loaded.
- `POST /analyze`: multipart `file` upload; optional UUID `analysis_id`.

Only JPEG, PNG and WebP are accepted. Maximum input size is 20 MB and maximum decoded dimensions are 40 megapixels. The service computes SHA-256 itself. Image bytes are sent to this standalone HTTP endpoint; Kafka job-reference integration is intentionally deferred until the repository's storage retrieval and orchestrator contracts are implemented.

## 5. Result semantics

- `status`: whether feature extraction executed successfully.
- `findings.outcome`: `inconclusive` until a validated attribution method is configured.
- `candidate_scores`: empty; no candidate ranking is fabricated.
- `attribution_supported`: false.
- Histogram values are normalized bin frequencies. Entropy is measured in bits.
- Edge response and spatial luminance variance are descriptive measurements, not calibrated evidence.

A future classifier must separately label raw classifier scores, similarity scores, calibrated probabilities and confidence estimates. They must never be interchanged.

## 6. Reproducibility and operations

Preprocessing is versioned in the returned feature profile. The current implementation uses Pillow RGB conversion, a maximum 256-pixel analysis side, bilinear resizing, grayscale conversion and a fixed tile grid. No model weights are loaded, so cold-start model loading and GPU measurements do not apply. CPU execution is the intended baseline.

Run tests from this directory:

```powershell
python -m pip install -r requirements.txt
pytest -q
```

The tests are authored but must be run in the target environment before the engine is considered validated. Do not commit model weights or secrets. Future artifacts must be versioned, checksum-verified, licence-reviewed and mounted/downloaded through an explicit deployment strategy.
