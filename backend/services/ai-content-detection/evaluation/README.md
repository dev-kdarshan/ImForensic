# AI Content Detection evaluation harness

The evaluation harness consumes a CSV of predictions produced by a separately configured detector. It does not run a model and does not generate predictions.

Required columns:

- `image_id`: stable sample identifier.
- `split`: `train`, `validation`, `calibration`, or `test`.
- `label`: `real` or `ai_generated`.
- `score`: numeric score where higher means more AI-like.
- `sha256`: source image SHA-256.
- `source`: dataset/source identifier.
- `generator`: generator family or `real_source`.
- `transformation`: `original`, `jpeg_q75`, `resize`, `crop`, `screenshot`, etc.

Run:

```bash
python evaluation/evaluate_predictions.py predictions.csv --split test --threshold 0.5 --score-semantics raw_score --output metrics.json
```

The threshold must be selected using a separate validation/calibration split and frozen before test evaluation. The script refuses a threshold inferred from the test set because it never searches for one. `raw_score` results are never called probabilities. Use `calibrated_probability` only when a separate calibration procedure has been fitted and documented.

Exact SHA-256 duplicates appearing in more than one split are rejected to reduce train/test leakage. This check does not detect perceptual near-duplicates; dataset curation must handle those separately.

Metrics include confusion matrix, precision, recall, F1, false-positive rate, balanced accuracy, and ROC-AUC. Grouped precision/recall/F1/FPR are reported by source, generator, and transformation where groups contain both classes. No target accuracy is preconfigured.
