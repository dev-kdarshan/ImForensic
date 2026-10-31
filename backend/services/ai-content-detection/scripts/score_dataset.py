#!/usr/bin/env python3
"""Run DDA over a labelled CSV manifest and write predictions for the evaluator.

Manifest columns: image_id,path,split,label,sha256,source,generator,transformation.
Paths are resolved relative to --root. The script never chooses a threshold.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dda_model import predict


FIELDS = ["image_id", "path", "split", "label", "sha256", "source", "generator", "transformation"]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_csv")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="predictions.csv")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()
    import os
    os.environ["DDA_DEVICE"] = args.device

    root = Path(args.root).resolve()
    with Path(args.manifest_csv).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    output = []
    for row in rows:
        path = (root / row["path"]).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Image path escapes dataset root: {row['path']}")
        actual = digest(path)
        if row["sha256"].strip().lower() != actual:
            raise ValueError(f"SHA-256 mismatch for {row['image_id']}")
        result = predict(path.read_bytes())
        output.append({
            **row,
            "score": result["score"],
            "score_semantics": "raw_score",
            "detector": result["detector"],
            "detector_version": result["detector_version"],
            "artifact_sha256": result["model_artifact"]["sha256"],
            "preprocessing_version": result["preprocessing_version"],
            "device": result["device"],
        })

    columns = FIELDS + ["score", "score_semantics", "detector", "detector_version", "artifact_sha256", "preprocessing_version", "device"]
    with Path(args.output).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output)
    print(f"Wrote {len(output)} predictions to {args.output}")


if __name__ == "__main__":
    main()
