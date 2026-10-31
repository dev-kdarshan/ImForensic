from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app import dda_model


def test_official_checkpoint_manifest_is_pinned():
    assert dda_model.CHECKPOINT_REPOSITORY == "Junwei-Xi/Dual-Data-Alignment"
    assert dda_model.CHECKPOINT_REVISION == "21a83bae9df37e5dd64ed995441764caf26ee1ab"
    assert dda_model.CHECKPOINT_SHA256 == "b27a31d39374803ddeff02bfabb2be76e190b04300490cddfafb24f683f37e3e"


def test_sha256_file(tmp_path):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"imforensic")
    assert dda_model.sha256_file(artifact) == hashlib.sha256(b"imforensic").hexdigest()


def test_checkpoint_required(monkeypatch):
    monkeypatch.delenv("DDA_CHECKPOINT_PATH", raising=False)
    with pytest.raises(dda_model.ModelNotConfigured):
        dda_model._checkpoint_path()


def test_device_rejects_unknown(monkeypatch):
    class FakeTorch:
        class device:
            def __init__(self, value):
                self.value = value
        class cuda:
            @staticmethod
            def is_available():
                return False
    monkeypatch.setenv("DDA_DEVICE", "tpu")
    with pytest.raises(dda_model.ModelNotConfigured):
        dda_model._resolve_device(FakeTorch)


def test_digest_mismatch_fails_before_torch_load(tmp_path, monkeypatch):
    artifact = tmp_path / "checkpoint.pth"
    artifact.write_bytes(b"not-a-model")
    monkeypatch.setenv("DDA_CHECKPOINT_PATH", str(artifact))
    with pytest.raises(dda_model.ModelArtifactError, match="SHA-256"):
        dda_model.load_model()
