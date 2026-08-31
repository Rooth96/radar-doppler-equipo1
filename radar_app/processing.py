"""Procesamiento Doppler genérico aplicado a una captura autocontenida."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from radar_app.captures import Capture


DETECTION_PROFILES = {
    "human": {
        "detection_mode": "LOW_DOPPLER_PERSISTENT_MULTIBIN",
        "min_doppler_hz": 0.9,
        "max_doppler_hz": 10.0,
        "threshold_db": 8.0,
        "baseline_instants": 10,
        "minimum_active_bins": 2,
        "minimum_hits": 2,
        "geometry_factor": 2.0,
        "status": "INITIAL_PROFILE_REQUIRES_CALIBRATION",
    },
    "vehicle": {
        "detection_mode": "VEHICLE_LOW_DOPPLER_PERSISTENT_MULTIBIN",
        "min_doppler_hz": 1.0,
        "max_doppler_hz": 10.0,
        "threshold_db": 8.0,
        "baseline_instants": 10,
        "minimum_active_bins": 4,
        "minimum_hits": 3,
        "geometry_factor": None,
        "status": "INITIAL_PROFILE_REQUIRES_CALIBRATION",
    },
    "baseline": {
        "detection_mode": "GENERAL_DOPPLER_PERSISTENT_MULTIBIN",
        "min_doppler_hz": 1.0,
        "max_doppler_hz": 150.0,
        "threshold_db": 8.0,
        "baseline_instants": 5,
        "minimum_active_bins": 3,
        "minimum_hits": 2,
        "geometry_factor": 2.0,
        "status": "INITIAL_PROFILE_REQUIRES_CALIBRATION",
    },
}


def ensure_detection_config(capture: Capture) -> dict[str, object]:
    path = capture.file("config", "detection_config.json")
    profile = dict(DETECTION_PROFILES.get(capture.kind, DETECTION_PROFILES["human"]))
    profile["case_name"] = capture.display_name
    if path.is_file():
        profile.update(_read_json(path))
    _write_json(path, profile)
    return profile


def process_capture(capture: Capture) -> dict[str, object]:
    config = ensure_detection_config(capture)
    sdr_config = _read_json(capture.file("config", "sdr_config.json"))
    frames = _read_frames(capture.file("raw", "waterfall.csv"))
    timestamps = list(frames)
    baseline_count = int(config.get("baseline_instants", 5))
    if len(timestamps) <= baseline_count:
        raise ValueError(
            f"La captura tiene {len(timestamps)} instantes y necesita más de "
            f"{baseline_count} para separar fondo y evaluación."
        )

    min_hz = float(config["min_doppler_hz"])
    max_hz = float(config["max_doppler_hz"])
    threshold_db = float(config["threshold_db"])
    minimum_bins = int(config.get("minimum_active_bins", 1))
    minimum_hits = int(config.get("minimum_hits", config.get("minimum_consecutive_hits", 1)))

    baseline_values: dict[float, list[float]] = defaultdict(list)
    for timestamp in timestamps[:baseline_count]:
        for frequency, power in frames[timestamp].items():
            if min_hz <= abs(frequency) <= max_hz:
                baseline_values[frequency].append(power)
    baseline = {frequency: median(values) for frequency, values in baseline_values.items()}
    if not baseline:
        raise ValueError(
            "La banda Doppler configurada no contiene bins. Revise la resolución espectral."
        )

    summaries = []
    current_hits = 0
    max_hits = 0
    for timestamp in timestamps[baseline_count:]:
        candidates = []
        active_absolute_bins = set()
        frame_excesses = []
        for frequency, power in frames[timestamp].items():
            if frequency not in baseline:
                continue
            excess = power - baseline[frequency]
            frame_excesses.append((frequency, power, baseline[frequency], excess))

        # Rechaza cambios de ganancia/potencia que elevan toda la banda por igual.
        # El Doppler buscado debe sobresalir respecto del cambio común del frame.
        common_mode_db = median(item[3] for item in frame_excesses) if frame_excesses else 0.0
        for frequency, power, baseline_power, excess in frame_excesses:
            localized_excess = excess - common_mode_db
            if localized_excess >= threshold_db:
                candidates.append((localized_excess, frequency, power, baseline_power))
                active_absolute_bins.add(round(abs(frequency), 6))
        frame_hit = len(active_absolute_bins) >= minimum_bins
        current_hits = current_hits + 1 if frame_hit else 0
        max_hits = max(max_hits, current_hits)
        representative = max(candidates, default=(0.0, 0.0, 0.0, 0.0))
        summaries.append({
            "timestamp": timestamp,
            "active_bins": len(active_absolute_bins),
            "frame_hit": frame_hit,
            "persistence_hits": current_hits,
            "excess_db": representative[0],
            "doppler_hz": representative[1],
            "peak_power_db": representative[2],
            "baseline_power_db": representative[3],
            "common_mode_db": common_mode_db,
        })

    runs = []
    current_run = []
    for row in summaries:
        if row["frame_hit"]:
            current_run.append(row)
        elif current_run:
            runs.append(current_run)
            current_run = []
    if current_run:
        runs.append(current_run)

    best_run = max(
        runs,
        key=lambda run: (len(run), max(row["excess_db"] for row in run)),
        default=[],
    )
    max_hits = len(best_run)
    detected = max_hits >= minimum_hits
    eligible = best_run if detected else summaries
    representative = max(eligible, key=lambda row: (row["persistence_hits"], row["excess_db"]))
    event_start = best_run[0]["timestamp"] if detected else None
    event_end = best_run[-1]["timestamp"] if detected else None
    doppler_hz = float(representative["doppler_hz"]) if detected else 0.0
    velocity = _estimate_velocity(doppler_hz, sdr_config, config) if detected else 0.0

    detection = {
        "case_name": capture.display_name.upper(),
        "detection_mode": config["detection_mode"],
        "timestamp": representative["timestamp"],
        "event_start": event_start,
        "event_end": event_end,
        "detected": detected,
        "doppler_hz": round(doppler_hz, 3),
        "snr_db": round(float(representative["excess_db"]), 3) if detected else 0.0,
        "excess_db": round(float(representative["excess_db"]), 3) if detected else 0.0,
        "peak_power_db": round(float(representative["peak_power_db"]), 3),
        "baseline_power_db": round(float(representative["baseline_power_db"]), 3),
        "common_mode_db": round(float(representative["common_mode_db"]), 3),
        "velocity_est_kmh": None if velocity is None else round(velocity, 2),
        "active_bins": int(representative["active_bins"]),
        "persistence_hits": max_hits,
        "minimum_active_bins": minimum_bins,
        "minimum_hits": minimum_hits,
        "baseline_instants": baseline_count,
        "rest_start": timestamps[0],
        "rest_end": timestamps[baseline_count - 1],
        "evaluation_start": timestamps[baseline_count],
        "total_instants": len(timestamps),
        "doppler_band_min_hz": min_hz,
        "doppler_band_max_hz": max_hz,
        "threshold_db": threshold_db,
        "validation_status": "PENDING_MANUAL_VALIDATION",
        "status": "PROCESSED_INITIAL_PROFILE",
    }
    events = []
    if detected:
        events.append({
            "timestamp": representative["timestamp"],
            "event_start": event_start,
            "event_end": event_end,
            "doppler_hz": detection["doppler_hz"],
            "snr_db": detection["snr_db"],
            "excess_db": detection["excess_db"],
            "active_bins": detection["active_bins"],
            "event_hits": max_hits,
            "velocity_est_kmh": detection["velocity_est_kmh"],
            "detected": True,
        })
    metrics = {
        "total_events": len(events),
        "average_snr_db": detection["snr_db"],
        "max_doppler_hz": abs(detection["doppler_hz"]),
        "max_velocity_kmh": detection["velocity_est_kmh"],
        "total_instants": len(timestamps),
        "baseline_instants": baseline_count,
        "evaluated_instants": len(summaries),
        "detection_rate_percent": None,
        "false_positive_rate_percent": None,
        "false_positives": None,
        "validation_status": "PENDING_GROUND_TRUTH",
    }

    _write_json(capture.file("processed", "detection_latest.json"), detection)
    _write_json(capture.file("processed", "metrics.json"), metrics)
    fields = [
        "timestamp", "event_start", "event_end", "doppler_hz", "snr_db",
        "excess_db", "active_bins", "event_hits", "velocity_est_kmh", "detected",
    ]
    _write_csv(capture.file("processed", "events.csv"), fields, events)
    return detection


def _read_frames(path: Path) -> dict[str, dict[float, float]]:
    frames: dict[str, dict[float, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"timestamp", "frequency_offset_hz", "power_db"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} no cumple el contrato espectral.")
        for row in reader:
            timestamp = row["timestamp"]
            frames.setdefault(timestamp, {})[float(row["frequency_offset_hz"])] = float(row["power_db"])
    if not frames:
        raise ValueError(f"{path} está vacío.")
    return frames


def _estimate_velocity(
    doppler_hz: float,
    sdr_config: dict[str, object],
    detection_config: dict[str, object],
) -> float | None:
    geometry_factor = detection_config.get("geometry_factor")
    if geometry_factor in (None, 0):
        return None
    wavelength = 299_792_458.0 / float(sdr_config["center_frequency_hz"])
    return abs(doppler_hz) * wavelength * 3.6 / float(geometry_factor)


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, data: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
