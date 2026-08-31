"""Orquestación local de adquisiciones y simulación sin hardware."""

from __future__ import annotations

import csv
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from radar_app.captures import Capture, CaptureRepository
from radar_app.processing import ensure_detection_config, process_capture


class CaptureOrchestrator:
    def __init__(self, repository: CaptureRepository):
        self.repository = repository

    def simulate(self, capture_id: str, seed: int = 1) -> Capture:
        """Genera una adquisición reproducible y sus resultados para probar la app."""
        capture = self.repository.update_status(capture_id, "capturing")
        try:
            self._write_simulated_config(capture)
            frames = self._generate_frames(seed)
            self._write_raw(capture, frames)
            self.repository.update_status(capture_id, "processing")
            self._write_results(capture, frames)
            return self.repository.update_status(capture_id, "completed")
        except Exception as error:
            self.repository.update_status(capture_id, "failed", str(error))
            raise

    def find_gnu_radio_python(self) -> Path | None:
        """Localiza un Python capaz de ejecutar el flowgraph en Windows."""
        configured = os.environ.get("RADAR_GNU_RADIO_PYTHON")
        candidates = [
            Path(configured) if configured else None,
            Path.home() / "radioconda" / "python.exe",
            Path("C:/radioconda/python.exe"),
            Path(sys.executable),
        ]
        return next((path.resolve() for path in candidates if path and path.is_file()), None)

    def check_gnu_radio_environment(self) -> dict[str, object]:
        python_path = self.find_gnu_radio_python()
        if python_path is None:
            return {"ready": False, "error": "No se encontró el Python de GNU Radio."}

        check = subprocess.run(
            [
                str(python_path),
                "-c",
                "import gnuradio, osmosdr, PyQt5, numpy; print('ready')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if check.returncode != 0:
            detail = (check.stderr or check.stdout).strip()
            return {"ready": False, "python": str(python_path), "error": detail}
        return {"ready": True, "python": str(python_path)}

    def build_hardware_command(
        self,
        capture_id: str,
        duration_seconds: float,
    ) -> tuple[list[str], dict[str, str]]:
        if duration_seconds <= 0:
            raise ValueError("La duración debe ser mayor que cero.")
        capture = self.repository.get(capture_id)
        environment = self.check_gnu_radio_environment()
        if not environment["ready"]:
            raise RuntimeError(str(environment.get("error", "GNU Radio no está disponible.")))

        flowgraph = Path(__file__).resolve().parents[1] / "gnu_radio" / "flowgraphs" / "untitled.py"
        if not flowgraph.is_file():
            raise FileNotFoundError(f"No se encontró el flowgraph exportado: {flowgraph}")

        process_environment = os.environ.copy()
        process_environment["RADAR_CAPTURE_DIR"] = str(capture.root.resolve())
        process_environment["RADAR_CAPTURE_DURATION_SECONDS"] = str(float(duration_seconds))
        detection_config = ensure_detection_config(capture)
        process_environment["RADAR_BASELINE_SECONDS"] = str(
            float(detection_config.get("baseline_instants", 5))
        )
        return [str(environment["python"]), str(flowgraph)], process_environment

    def run_hardware_capture(self, capture_id: str, duration_seconds: float) -> Capture:
        """Ejecuta GNU Radio de forma síncrona y conserva su registro."""
        capture = self.repository.get(capture_id)
        detection_config = ensure_detection_config(capture)
        capture = self.repository.update_metadata(
            capture_id,
            acquisition_mode="rtl_sdr",
            requested_duration_seconds=float(duration_seconds),
            baseline_seconds=float(detection_config.get("baseline_instants", 5)),
        )
        command, environment = self.build_hardware_command(capture_id, duration_seconds)
        self.repository.update_status(capture_id, "capturing")
        log_path = capture.root / "capture.log"

        try:
            result = subprocess.run(
                command,
                cwd=str(Path(command[1]).parent),
                env=environment,
                capture_output=True,
                text=True,
                timeout=duration_seconds + 30,
                check=False,
            )
            log_path.write_text(
                result.stdout + ("\n--- STDERR ---\n" + result.stderr if result.stderr else ""),
                encoding="utf-8",
            )
            if result.returncode != 0:
                raise RuntimeError(f"GNU Radio terminó con código {result.returncode}. Revise {log_path.name}.")
            missing = [
                path.name
                for path in (
                    capture.file("raw", "spectrum_latest.csv"),
                    capture.file("raw", "waterfall.csv"),
                    capture.file("config", "sdr_config.json"),
                )
                if not path.is_file() or path.stat().st_size == 0
            ]
            if missing:
                raise RuntimeError(f"GNU Radio no generó archivos válidos: {', '.join(missing)}")
            self.repository.update_status(capture_id, "captured")
            return self.process_existing_capture(capture_id)
        except Exception as error:
            self.repository.update_status(capture_id, "failed", str(error))
            raise

    def process_existing_capture(self, capture_id: str) -> Capture:
        capture = self.repository.update_status(capture_id, "processing")
        try:
            process_capture(capture)
            return self.repository.update_status(capture_id, "completed")
        except Exception as error:
            self.repository.update_status(capture_id, "failed", str(error))
            raise

    @staticmethod
    def _write_simulated_config(capture: Capture) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        sdr_config = {
            "timestamp": now,
            "center_frequency_hz": 99_300_000,
            "sample_rate_hz": 240_000,
            "gain_db": 20.0,
            "fft_size": 32_768,
            "frequency_resolution_hz": 0.5,
            "window_type": "blackman-harris",
            "source_device": "SIMULATED",
        }
        detection_config = {
            "status": "SIMULATION",
            "min_doppler_hz": 1.0,
            "max_doppler_hz": 10.0,
            "threshold_db": 8.0,
            "minimum_active_bins": 3,
            "minimum_hits": 3,
            "baseline_instants": 5,
        }
        _write_json(capture.file("config", "sdr_config.json"), sdr_config)
        _write_json(capture.file("config", "detection_config.json"), detection_config)

    @staticmethod
    def _generate_frames(seed: int) -> list[dict[str, object]]:
        randomizer = random.Random(seed)
        start = datetime.now().astimezone().replace(microsecond=0)
        rows = []
        for frame_index in range(20):
            timestamp = (start + timedelta(seconds=frame_index)).isoformat(timespec="milliseconds")
            event_active = 8 <= frame_index <= 13
            for frequency in range(-10, 11):
                noise = -82.0 + randomizer.uniform(-1.2, 1.2)
                signal = 15.0 if event_active and abs(frequency) in {3, 4, 5} else 0.0
                rows.append({
                    "timestamp": timestamp,
                    "frequency_offset_hz": float(frequency),
                    "power_db": round(noise + signal, 3),
                })
        return rows

    @staticmethod
    def _write_raw(capture: Capture, frames: list[dict[str, object]]) -> None:
        fields = ["timestamp", "frequency_offset_hz", "power_db"]
        _write_csv(capture.file("raw", "waterfall.csv"), fields, frames)
        latest_timestamp = frames[-1]["timestamp"]
        latest = [row for row in frames if row["timestamp"] == latest_timestamp]
        _write_csv(capture.file("raw", "spectrum_latest.csv"), fields, latest)

    @staticmethod
    def _write_results(capture: Capture, frames: list[dict[str, object]]) -> None:
        timestamps = list(dict.fromkeys(str(row["timestamp"]) for row in frames))
        event_start, event_end = timestamps[8], timestamps[13]
        wavelength = 299_792_458 / 99_300_000
        velocity = 4.0 * wavelength * 3.6
        detection = {
            "case_name": capture.display_name.upper(),
            "detection_mode": "SIMULATED_DOPPLER_EVENT",
            "timestamp": event_end,
            "event_start": event_start,
            "event_end": event_end,
            "detected": True,
            "doppler_hz": 4.0,
            "snr_db": 15.0,
            "excess_db": 15.0,
            "velocity_est_kmh": round(velocity, 2),
            "active_bins": 3,
            "persistence_hits": 6,
            "minimum_active_bins": 3,
            "minimum_hits": 3,
            "known_speed_kmh": 30.0,
            "doppler_band_min_hz": 1.0,
            "doppler_band_max_hz": 10.0,
            "threshold_db": 8.0,
            "expected_max_doppler_hz": 5.52,
            "status": "SIMULATED",
        }
        metrics = {
            "total_events": 1,
            "average_snr_db": 15.0,
            "max_doppler_hz": 4.0,
            "max_velocity_kmh": round(velocity, 2),
            "detection_rate_percent": 100.0,
            "false_positive_rate_percent": 0.0,
            "false_positives": 0,
            "total_instants": 20,
            "baseline_instants": 8,
        }
        events = [{
            "timestamp": event_end,
            "event_start": event_start,
            "event_end": event_end,
            "doppler_hz": 4.0,
            "snr_db": 15.0,
            "excess_db": 15.0,
            "active_bins": 3,
            "event_hits": 6,
            "velocity_est_kmh": round(velocity, 2),
            "detected": True,
        }]
        _write_json(capture.file("processed", "detection_latest.json"), detection)
        _write_json(capture.file("processed", "metrics.json"), metrics)
        _write_csv(capture.file("processed", "events.csv"), list(events[0]), events)


def _write_json(path: Path, data: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
