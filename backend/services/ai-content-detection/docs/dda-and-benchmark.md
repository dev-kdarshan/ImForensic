# DDA inference and independent benchmark

## Verified upstream artifact

- Official code: https://github.com/roy-ch/Dual-Data-Alignment
- Code revision inspected: `08d6b414a33826403b9096cfdb7758d5eae12dbb`
- Official checkpoint repository: `Junwei-Xi/Dual-Data-Alignment`
- Checkpoint revision: `21a83bae9df37e5dd64ed995441764caf26ee1ab`
- File: `DDA_ckpt.pth`, 1,255,621,296 bytes
- SHA-256: `b27a31d39374803ddeff02bfabb2be76e190b04300490cddfafb24f683f37e3e`
- Official code license: Apache-2.0; the Hugging Face model card declares Apache-2.0. Verify all third-party backbone and data rights separately.
- DINOv2 code is pinned to `7b187bd4df8efce2cbcbbb67bd01532c19bf4c9`; its model card declares Apache-2.0 for the ViT-L/14 model. Pretrained backbone weights are fetched by Torch Hub on first initialization and should be cached in a controlled model volume.

The official repository README explicitly announces a February 2026 corrected checkpoint because an earlier upload differed slightly from the paper results. Use the pinned new official checkpoint, not the legacy artifact. Artifact hash and size are taken from the official Hugging Face Xet metadata. The application does not download or commit the checkpoint.

## Security and loading

The official inference example uses unrestricted `torch.load` and a floating Torch Hub reference. This integration intentionally does not copy those unsafe defaults:
- verify the local checkpoint SHA-256 before deserialization;
- use `torch.load(..., weights_only=True, map_location="cpu")`;
- require a mapping of string keys to tensors under the `model` key and strict state-dict loading;
- pin the DDA architecture source revision and DINOv2 code revision;
- never accept a user-supplied checkpoint path or arbitrary remote repository;
- mount the checkpoint read-only and keep it outside Git.

A safe load is only as trustworthy as the verified artifact and the pinned model code. Review Torch/PyTorch vulnerability advisories and model supply chain before production.

## Preprocessing and score meaning

The inspected official inference script uses RGB conversion, `CenterCrop(336)`, `ToTensor()`, and CLIP normalization:
- mean: [0.48145466, 0.4578275, 0.40821073]
- std: [0.26862954, 0.26130258, 0.27577711]

This adapter applies EXIF orientation before RGB conversion as a deliberate input-normalization policy; it is recorded in result metadata. The official DDA repository notes that JPEG decoder versions affect reproduced results and recommends Pillow 12.3.0 with libjpeg-turbo 3.1.4.1 for its reported benchmark reproduction. Pillow is pinned here; the container's libjpeg-turbo version must still be checked and matched before comparing benchmark figures. No resize is applied: images smaller than the crop size may be padded by torchvision CenterCrop semantics.

The score is `sigmoid(raw_logit)`, oriented higher = more AI-generated/synthetic-like under the DDA label convention. It is a bounded model score, **not a calibrated probability**, not confidence of authenticity, and not evidence of provenance. The API currently emits an unthresholded score only. It does not declare an AI/real decision. A decision threshold must be selected on a separate validation/calibration split and then frozen before test evaluation.

## Install and run

Install the CPU or CUDA-specific PyTorch wheel appropriate for the target host from https://pytorch.org/get-started/locally/, then:

```bash
cd backend/services/ai-content-detection
python -m pip install -r requirements.txt
python -m pip install -r requirements-model.txt
export DDA_CHECKPOINT_PATH=/models/DDA_ckpt.pth
export DDA_CHECKPOINT_SHA256=b27a31d39374803ddeff02bfabb2be76e190b04300490cddfafb24f683f37e3e
export DDA_DEVICE=auto  # auto | cpu | cuda
python scripts/check_runtime.py
uvicorn app.main:app --host 0.0.0.0 --port 8004
```

First model initialization requires access to the pinned DINOv2 source and pretrained backbone weights, unless already cached. The checkpoint is about 1.26 GB; reserve disk, RAM and VRAM headroom. GPU availability does not guarantee sufficient VRAM. CPU inference may be very slow; measure on the actual deployment hardware. No CPU/GPU performance claim is made by this change.

## Independent benchmark

Prepare a reviewed manifest CSV with columns:
`image_id,path,split,label,sha256,source,generator,transformation`.

Use only datasets whose source terms permit your intended use. The DDA authors recommend reporting results on their expanded evaluation benchmarks; their published figures are research results, not ImForensic results. Keep training/validation/test source-disjoint where possible and hold out generator families for unseen-generator evaluation. Exclude uncertain and AI-edited examples from this first binary task. Exact hash leakage is checked by the evaluator; perceptual near-duplicate review remains a dataset-curation task.

Generate predictions without threshold tuning:

```bash
python scripts/score_dataset.py manifest.csv --root /datasets/dda-eval --device auto --output predictions.csv
python evaluation/evaluate_predictions.py predictions.csv --split validation --threshold 0.5 --score-semantics raw_score --output validation-metrics.json
python evaluation/evaluate_predictions.py predictions.csv --split test --threshold 0.5 --score-semantics raw_score --output test-metrics.json
```

The threshold above is an example only. Choose and freeze an operating threshold using validation/calibration data, then pass that same value for test reporting. Do not use test data to select or calibrate a threshold. The evaluator reports confusion matrix, precision, recall, F1, FPR, specificity, balanced accuracy, ROC-AUC, and grouped results. ROC-AUC measures ranking, not calibration. Add perceptual near-duplicate detection and dataset rights review before treating results as an independent benchmark.

## Status and gates

This PR adds the inference adapter and benchmark runner but does not download the model or datasets. It does not claim inference, CPU/GPU compatibility, or benchmark execution has succeeded. Before enabling this detector outside a controlled experiment:
1. install pinned dependencies in CPU and target GPU environments;
2. verify the checkpoint digest from the actual downloaded file;
3. load the model and compare preprocessing/logit outputs against the official inference script on fixed fixtures;
4. run representative CPU and GPU memory/latency tests;
5. run source-disjoint and generator-disjoint benchmarks;
6. decide whether a calibration step is warranted using held-out validation data;
7. define false-positive acceptance criteria before production.
