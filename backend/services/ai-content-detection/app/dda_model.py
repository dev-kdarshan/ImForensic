"""Verified, lazy-loaded DDA inference adapter.

The checkpoint is never downloaded automatically and is never loaded with unrestricted
pickle deserialization. Configure DDA_CHECKPOINT_PATH and the pinned SHA-256 explicitly.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import Lock

from PIL import Image
from PIL import ImageOps

CHECKPOINT_SHA256 = "b27a31d39374803ddeff02bfabb2be76e190b04300490cddfafb24f683f37e3e"
CHECKPOINT_REVISION = "21a83bae9df37e5dd64ed995441764caf26ee1ab"
CHECKPOINT_REPOSITORY = "Junwei-Xi/Dual-Data-Alignment"
CHECKPOINT_FILENAME = "DDA_ckpt.pth"
DDA_CODE_REVISION = "08d6b414a33826403b9096cfdb7758d5eae12dbb"
DINOV2_CODE_REVISION = "7b187bd4df8efce2cbcbbb67bd01532c19bf4c9c"
DETECTOR_NAME = "DDA"
DETECTOR_VERSION = f"official-checkpoint-{CHECKPOINT_REVISION[:12]}"
PREPROCESSING_VERSION = "dda-official-centercrop336-clipnorm-v1"

_lock = Lock()
_model = None
_device = None
_transform = None


class ModelNotConfigured(RuntimeError):
    pass


class ModelArtifactError(RuntimeError):
    pass


def _checkpoint_path() -> Path:
    raw = os.getenv("DDA_CHECKPOINT_PATH", "").strip()
    if not raw:
        raise ModelNotConfigured("DDA_CHECKPOINT_PATH is not configured.")
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ModelNotConfigured("Configured DDA checkpoint file does not exist.")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_device(torch):
    requested = os.getenv("DDA_DEVICE", "auto").strip().lower()
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise ModelNotConfigured("DDA_DEVICE=cuda requested but CUDA is unavailable.")
        return torch.device("cuda:0")
    if requested == "cpu":
        return torch.device("cpu")
    raise ModelNotConfigured("DDA_DEVICE must be auto, cpu, or cuda.")


def load_model():
    global _model, _device, _transform
    with _lock:
        if _model is not None:
            return _model, _device, _transform
        path = _checkpoint_path()
        expected = os.getenv("DDA_CHECKPOINT_SHA256", CHECKPOINT_SHA256).strip().lower()
        if expected != CHECKPOINT_SHA256:
            raise ModelArtifactError("Configured checkpoint digest does not match the pinned official digest.")
        actual = sha256_file(path)
        if actual != CHECKPOINT_SHA256:
            raise ModelArtifactError("DDA checkpoint SHA-256 verification failed.")

        try:
            import torch
            from torchvision import transforms
            from app.dda_architecture import DINOv2ModelWithLoRA
        except ImportError as exc:
            raise ModelNotConfigured("Install requirements-model.txt to enable DDA inference.") from exc

        device = _resolve_device(torch)
        try:
            model = DINOv2ModelWithLoRA()
            # weights_only=True prevents arbitrary Python object deserialization.
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
            if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("model"), dict):
                raise ModelArtifactError("Checkpoint must contain a tensor state dictionary at key 'model'.")
            state = checkpoint["model"]
            if not all(isinstance(key, str) and isinstance(value, torch.Tensor) for key, value in state.items()):
                raise ModelArtifactError("Checkpoint contains non-tensor state entries.")
            model.load_state_dict(state, strict=True)
            model.to(device)
            model.eval()
        except ModelArtifactError:
            raise
        except Exception as exc:
            raise ModelArtifactError(f"DDA model initialization failed: {type(exc).__name__}: {exc}") from exc

        _model = model
        _device = device
        _transform = transforms.Compose([
            transforms.CenterCrop(336),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.48145466, 0.4578275, 0.40821073],
                std=[0.26862954, 0.26130258, 0.27577711],
            ),
        ])
        return _model, _device, _transform


def model_status() -> dict:
    if not os.getenv("DDA_CHECKPOINT_PATH", "").strip():
        return {"configured": False, "reason": "MODEL_NOT_CONFIGURED"}
    try:
        model, device, _ = load_model()
        return {"configured": model is not None, "device": str(device), "detector": DETECTOR_NAME}
    except Exception as exc:
        return {"configured": False, "reason": "MODEL_LOAD_FAILED", "detail": str(exc)}


def predict(content: bytes) -> dict:
    import torch

    model, device, transform = load_model()
    with Image.open(__import__("io").BytesIO(content)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)
    with torch.inference_mode():
        logit = model(tensor).reshape(-1)[0]
        score = float(torch.sigmoid(logit).detach().cpu().item())
    if not 0.0 <= score <= 1.0:
        raise ModelArtifactError("DDA returned a non-finite or out-of-range score.")
    return {
        "detector": DETECTOR_NAME,
        "detector_version": DETECTOR_VERSION,
        "model_artifact": {
            "repository": CHECKPOINT_REPOSITORY,
            "revision": CHECKPOINT_REVISION,
            "filename": CHECKPOINT_FILENAME,
            "sha256": CHECKPOINT_SHA256,
        },
        "preprocessing_version": PREPROCESSING_VERSION,
        "device": str(device),
        "raw_logit": float(logit.detach().cpu().item()),
        "score": score,
        "score_semantics": (
            "sigmoid(raw_logit), oriented so higher values indicate more AI-generated/synthetic-like "
            "according to the DDA training label convention; this is an uncalibrated model score, "
            "not a calibrated probability or a confidence of authenticity."
        ),
    }
