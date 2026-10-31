#!/usr/bin/env python3
"""Evaluate precomputed AI-image detector scores without tuning on the test split."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


REQUIRED = {"image_id", "split", "label", "score", "sha256", "source", "generator", "transformation"}
LABELS = {"real", "ai_generated"}


def auc_roc(rows):
    positives = [row["score"] for row in rows if row["label"] == "ai_generated"]
    negatives = [row["score"] for row in rows if row["label"] == "real"]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += 1.0 if positive > negative else 0.5 if positive == negative else 0.0
    return wins / (len(positives) * len(negatives))


def metrics(rows, threshold):
    tp = fp = tn = fn = 0
    for row in rows:
        predicted_ai = row["score"] >= threshold
        actual_ai = row["label"] == "ai_generated"
        if predicted_ai and actual_ai:
            tp += 1
        elif predicted_ai and not actual_ai:
            fp += 1
        elif not predicted_ai and not actual_ai:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "n": len(rows),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
        "specificity": specificity,
        "balanced_accuracy": (recall + specificity) / 2 if (tp + fn and tn + fp) else None,
        "roc_auc": auc_roc(rows),
    }


def load_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        rows = []
        for line_number, raw in enumerate(reader, start=2):
            if raw["label"] not in LABELS:
                raise ValueError(f"Line {line_number}: label must be real or ai_generated.")
            try:
                score = float(raw["score"])
            except ValueError:
                raise ValueError(f"Line {line_number}: score must be numeric.") from None
            if not math.isfinite(score):
                raise ValueError(f"Line {line_number}: score must be finite.")
            rows.append({**raw, "score": score})
    return rows


def check_split_leakage(rows):
    digest_splits = defaultdict(set)
    for row in rows:
        digest = row["sha256"].strip().lower()
        if digest:
            digest_splits[digest].add(row["split"])
    leaked = [digest for digest, splits in digest_splits.items() if len(splits) > 1]
    if leaked:
        raise ValueError(f"Found {len(leaked)} exact SHA-256 duplicates across splits.")


def grouped_metrics(rows, field, threshold):
    groups = defaultdict(list)
    for row in rows:
        groups[row[field] or "unspecified"].append(row)
    return {
        name: metrics(group, threshold)
        for name, group in sorted(groups.items())
        if {row["label"] for row in group} == LABELS
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions_csv")
    parser.add_argument("--split", choices=["validation", "calibration", "test"], required=True)
    parser.add_argument("--threshold", type=float, required=True,
                        help="Frozen threshold selected on a separate validation/calibration set.")
    parser.add_argument("--score-semantics", choices=["raw_score", "calibrated_probability"],
                        default="raw_score")
    parser.add_argument("--output", default="metrics.json")
    args = parser.parse_args()

    rows = load_rows(args.predictions_csv)
    check_split_leakage(rows)
    selected = [row for row in rows if row["split"] == args.split]
    if not selected:
        raise ValueError(f"No rows found for split {args.split!r}.")
    if {row["label"] for row in selected} != LABELS:
        raise ValueError("Selected split must contain both real and ai_generated samples.")
    if args.score_semantics == "calibrated_probability":
        if not 0.0 <= args.threshold <= 1.0 or any(not 0.0 <= row["score"] <= 1.0 for row in selected):
            raise ValueError("Calibrated probabilities and their threshold must be within [0, 1].")

    report = {
        "split": args.split,
        "threshold": args.threshold,
        "score_semantics": args.score_semantics,
        "score_direction": "higher_is_more_ai_like",
        "metrics": metrics(selected, args.threshold),
        "by_source": grouped_metrics(selected, "source", args.threshold),
        "by_generator": grouped_metrics(selected, "generator", args.threshold),
        "by_transformation": grouped_metrics(selected, "transformation", args.threshold),
        "limitations": [
            "This script evaluates supplied predictions; it does not validate their provenance or model implementation.",
            "Exact SHA-256 split leakage is checked; perceptual near-duplicates require separate curation.",
            "ROC-AUC is ranking performance and does not establish probability calibration.",
            "The threshold is supplied and frozen; it is never selected on this split.",
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
