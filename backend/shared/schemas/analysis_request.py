"""Versioned, storage-reference-only analysis request contract."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import ClassVar
from urllib.parse import urlsplit
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    SCHEMA_VERSION: ClassVar[str] = "1.0.0"
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    image_ref: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    requested_engines: list[str] = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = Field(default=None, max_length=128)
    ALLOWED_ENGINES: ClassVar[set[str]] = {"metadata-provenance", "model-fingerprint", "pixel-forensics", "ai-content-detection", "watermark-detection", "visual-consistency"}

    @field_validator("analysis_id")
    @classmethod
    def valid_analysis_id(cls, value: str) -> str:
        try:
            return str(UUID(value))
        except ValueError:
            raise ValueError("analysis_id must be a UUID") from None

    @field_validator("image_ref")
    @classmethod
    def secure_storage_reference(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"storage", "s3", "gs", "https"} or not parsed.netloc:
            raise ValueError("image_ref must be an opaque storage://, s3://, gs:// or HTTPS reference")
        if ".." in parsed.path.split("/") or "\\\\" in value:
            raise ValueError("image_ref must not contain path traversal")
        return value

    @field_validator("requested_engines")
    @classmethod
    def supported_engines_only(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("requested_engines must not contain duplicates")
        unknown = sorted(set(value) - cls.ALLOWED_ENGINES)
        if unknown:
            raise ValueError(f"Unsupported engine(s): {', '.join(unknown)}")
        return value
