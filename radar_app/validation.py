"""Registro de observaciones manuales y métricas validadas por captura."""

from __future__ import annotations

import csv
import json
from datetime import datetime

from radar_app.captures import Capture, CaptureRepository


def record_validation(
    capture: Capture,
    movement_observed: bool,
    notes: str = "",
) -> dict[str, object]:
    detection_path = capture.file("processed", "detection_latest.json")
    metrics_path = capture.file("processed", "metrics.json")
    detection = _read_json(detection_path)
    metrics = _read_json(metrics_path)
    predicted = bool(detection["detected"])
    actual = bool(movement_observed)
    outcome = classify_outcome(predicted, actual)
    validated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    row = {
        "validated_at": validated_at,
        "detection_timestamp": detection.get("timestamp", ""),
        "predicted_movement": predicted,
        "observed_movement": actual,
        "outcome": outcome,
        "notes": notes.strip(),
    }
    ground_truth_path = capture.file("processed", "ground_truth.csv")
    # Una captura representa un ensayo. Una nueva observación corrige la anterior
    # en vez de inflar las métricas como si fuera otro experimento.
    rows = [row]
    _write_csv(ground_truth_path, list(row), rows)

    counts = {label: 0 for label in ("TP", "TN", "FP", "FN")}
    for validation in rows:
        label = validation.get("outcome")
        if label in counts:
            counts[label] += 1
    total = sum(counts.values())
    actual_positives = counts["TP"] + counts["FN"]
    actual_negatives = counts["TN"] + counts["FP"]

    metrics.update({
        "true_positives": counts["TP"],
        "true_negatives": counts["TN"],
        "false_positives": counts["FP"],
        "false_negatives": counts["FN"],
        "validated_trials": total,
        "accuracy_percent": _percent(counts["TP"] + counts["TN"], total),
        "detection_rate_percent": _percent(counts["TP"], actual_positives),
        "false_positive_rate_percent": _percent(counts["FP"], actual_negatives),
        "validation_status": "VALIDATED_MANUALLY",
    })
    detection.update({
        "observed_movement": actual,
        "validation_outcome": outcome,
        "validated_at": validated_at,
        "validation_status": "VALIDATED_MANUALLY",
    })
    _write_json(metrics_path, metrics)
    _write_json(detection_path, detection)
    return row


def classify_outcome(predicted: bool, actual: bool) -> str:
    if predicted and actual:
        return "TP"
    if predicted and not actual:
        return "FP"
    if not predicted and actual:
        return "FN"
    return "TN"


def summarize_repository(repository: CaptureRepository) -> dict[str, object]:
    trials = []
    captures = repository.discover()
    for capture in captures:
        ground_truth_path = capture.file("processed", "ground_truth.csv")
        validation = _latest_validation(ground_truth_path)
        if validation is None:
            continue
        trials.append({
            "capture_id": capture.capture_id,
            "name": capture.display_name,
            "kind": capture.kind,
            "created_at": capture.metadata["created_at"],
            "predicted_movement": _csv_bool(validation["predicted_movement"]),
            "observed_movement": _csv_bool(validation["observed_movement"]),
            "outcome": validation["outcome"],
            "validated_at": validation["validated_at"],
            "notes": validation.get("notes", ""),
        })

    return {
        "overall": _summarize_trials(trials),
        "by_kind": {
            kind: _summarize_trials([trial for trial in trials if trial["kind"] == kind])
            for kind in ("human", "vehicle", "baseline", "unknown")
            if any(trial["kind"] == kind for trial in trials)
        },
        "trials": trials,
        "unvalidated_captures": len(captures) - len(trials),
    }


def _summarize_trials(trials: list[dict[str, object]]) -> dict[str, object]:
    counts = {label: 0 for label in ("TP", "TN", "FP", "FN")}
    for trial in trials:
        outcome = str(trial["outcome"])
        if outcome in counts:
            counts[outcome] += 1
    total = sum(counts.values())
    positives = counts["TP"] + counts["FN"]
    negatives = counts["TN"] + counts["FP"]
    return {
        "total": total,
        **counts,
        "accuracy_percent": _percent(counts["TP"] + counts["TN"], total),
        "detection_rate_percent": _percent(counts["TP"], positives),
        "false_positive_rate_percent": _percent(counts["FP"], negatives),
    }


def _latest_validation(path):
    if not path.is_file() or path.stat().st_size == 0:
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    required = {
        "validated_at", "predicted_movement", "observed_movement", "outcome"
    }
    valid = [row for row in rows if required.issubset(row) and row.get("outcome") in {"TP", "TN", "FP", "FN"}]
    return valid[-1] if valid else None


def _csv_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "sí", "si"}


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100.0 * numerator / denominator, 2) if denominator else None


def _read_json(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
