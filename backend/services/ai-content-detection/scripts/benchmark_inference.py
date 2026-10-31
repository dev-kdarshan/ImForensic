#!/usr/bin/env python3
"""Measure DDA warm inference latency and CUDA peak memory on the current host."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.warmup < 0 or args.runs < 1:
        parser.error("--warmup must be >= 0 and --runs must be >= 1")
    os.environ["DDA_DEVICE"] = args.device

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import torch
    from app.dda_model import predict

    content = Path(args.image).read_bytes()
    # The first call includes model initialization and is deliberately excluded
    # from warm latency statistics.
    started = time.perf_counter()
    first = predict(content)
    cold_seconds = time.perf_counter() - started
    for _ in range(args.warmup):
        predict(content)
    if first["device"].startswith("cuda"):
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    timings = []
    for _ in range(args.runs):
        started = time.perf_counter()
        predict(content)
        if first["device"].startswith("cuda"):
            torch.cuda.synchronize()
        timings.append(time.perf_counter() - started)
    report = {
        "device": first["device"],
        "detector": first["detector"],
        "cold_start_seconds": round(cold_seconds, 4),
        "warm_runs": args.runs,
        "warm_latency_mean_seconds": round(statistics.mean(timings), 4),
        "warm_latency_median_seconds": round(statistics.median(timings), 4),
        "warm_latency_p95_seconds": round(sorted(timings)[min(len(timings) - 1, int(0.95 * len(timings)))], 4),
        "images_per_second": round(1.0 / statistics.mean(timings), 4),
        "cuda_peak_allocated_bytes": (
            torch.cuda.max_memory_allocated() if first["device"].startswith("cuda") else None
        ),
        "score_semantics": "uncalibrated sigmoid(logit), higher means more AI-generated-like",
        "note": "Measurements are host-specific; compare only with the same image, decoder and runtime versions.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
