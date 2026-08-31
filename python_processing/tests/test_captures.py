import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from radar_app.captures import CaptureRepository
from radar_app.orchestrator import CaptureOrchestrator
from radar_app.processing import process_capture
from radar_app.validation import classify_outcome, record_validation, summarize_repository


class TestCaptureRepository(unittest.TestCase):
    def test_create_builds_the_complete_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")

            capture = repository.create(
                "Vehículo frente al laboratorio",
                kind="vehicle",
                notes="Prueba controlada",
            )

            self.assertIn("vehiculo-frente-al-laboratorio", capture.capture_id)
            self.assertEqual(capture.display_name, "Vehículo frente al laboratorio")
            self.assertTrue(capture.config_dir.is_dir())
            self.assertTrue(capture.raw_dir.is_dir())
            self.assertTrue(capture.processed_dir.is_dir())
            self.assertTrue((capture.root / "metadata.json").is_file())

    def test_discover_uses_metadata_and_orders_newest_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            captures_dir = Path(temp_dir) / "captures"
            repository = CaptureRepository(captures_dir)
            first = repository.create("Primera")
            second = repository.create("Segunda")

            first_metadata_path = first.root / "metadata.json"
            first_metadata = json.loads(first_metadata_path.read_text(encoding="utf-8"))
            first_metadata["created_at"] = "2025-01-01T00:00:00-04:00"
            first_metadata_path.write_text(
                json.dumps(first_metadata, ensure_ascii=False),
                encoding="utf-8",
            )

            discovered = repository.discover()

            self.assertEqual(discovered[0].capture_id, second.capture_id)
            self.assertEqual({item.display_name for item in discovered}, {"Primera", "Segunda"})

    def test_invalid_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            capture_dir = Path(temp_dir) / "captures" / "incompleta"
            for section in ("config", "raw", "processed"):
                (capture_dir / section).mkdir(parents=True)
            (capture_dir / "metadata.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "faltan metadatos"):
                CaptureRepository(Path(temp_dir) / "captures").discover()

    def test_simulation_completes_a_new_capture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            capture = repository.create("Ensayo simulado", kind="human")

            completed = CaptureOrchestrator(repository).simulate(capture.capture_id)

            self.assertEqual(completed.metadata["status"], "completed")
            self.assertTrue(completed.file("raw", "waterfall.csv").is_file())
            self.assertTrue(completed.file("raw", "spectrum_latest.csv").is_file())
            self.assertTrue(completed.file("processed", "detection_latest.json").is_file())
            detection = json.loads(
                completed.file("processed", "detection_latest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(detection["detected"])

    def test_hardware_command_targets_selected_capture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            capture = repository.create("Captura real", kind="human")
            orchestrator = CaptureOrchestrator(repository)

            with patch.object(
                orchestrator,
                "check_gnu_radio_environment",
                return_value={"ready": True, "python": "C:/radioconda/python.exe"},
            ):
                command, environment = orchestrator.build_hardware_command(
                    capture.capture_id,
                    duration_seconds=30,
                )

            self.assertEqual(command[0], "C:/radioconda/python.exe")
            self.assertEqual(environment["RADAR_CAPTURE_DIR"], str(capture.root.resolve()))
            self.assertEqual(environment["RADAR_CAPTURE_DURATION_SECONDS"], "30.0")

    def test_hardware_run_marks_valid_acquisition_as_captured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            capture = repository.create("Captura RTL", kind="human")
            flowgraph = Path(temp_dir) / "untitled.py"
            flowgraph.write_text("# test", encoding="utf-8")
            for path in (
                capture.file("raw", "spectrum_latest.csv"),
                capture.file("raw", "waterfall.csv"),
                capture.file("config", "sdr_config.json"),
            ):
                path.write_text("data", encoding="utf-8")

            orchestrator = CaptureOrchestrator(repository)
            with (
                patch.object(
                    orchestrator,
                    "build_hardware_command",
                    return_value=(["python", str(flowgraph)], {}),
                ),
                patch.object(
                    orchestrator,
                    "process_existing_capture",
                    side_effect=lambda capture_id: repository.update_status(capture_id, "completed"),
                ),
                patch(
                    "radar_app.orchestrator.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, "GNU Radio OK", ""),
                ),
            ):
                result = orchestrator.run_hardware_capture(capture.capture_id, 5)

            self.assertEqual(result.metadata["status"], "completed")
            self.assertIn("GNU Radio OK", (capture.root / "capture.log").read_text(encoding="utf-8"))

    def test_generic_processor_detects_simulated_persistent_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            capture = repository.create("Procesamiento genérico", kind="human")
            completed = CaptureOrchestrator(repository).simulate(capture.capture_id)

            detection = process_capture(completed)

            self.assertTrue(detection["detected"])
            self.assertGreaterEqual(detection["persistence_hits"], detection["minimum_hits"])

    def test_manual_validation_updates_detection_and_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            capture = repository.create("Validación", kind="human")
            completed = CaptureOrchestrator(repository).simulate(capture.capture_id)

            validation = record_validation(completed, True, "Movimiento observado")

            self.assertEqual(validation["outcome"], "TP")
            metrics = json.loads(
                completed.file("processed", "metrics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metrics["true_positives"], 1)
            self.assertEqual(metrics["accuracy_percent"], 100.0)
            self.assertEqual(metrics["validated_trials"], 1)

    def test_validation_correction_replaces_previous_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            capture = repository.create("Corrección", kind="human")
            completed = CaptureOrchestrator(repository).simulate(capture.capture_id)

            record_validation(completed, True)
            correction = record_validation(completed, False, "Corrección del observador")

            self.assertEqual(correction["outcome"], "FP")
            rows = completed.file("processed", "ground_truth.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 2)
            metrics = json.loads(
                completed.file("processed", "metrics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metrics["false_positives"], 1)
            self.assertEqual(metrics["true_positives"], 0)

    def test_validation_classifies_confusion_matrix(self):
        expected = {
            (True, True): "TP",
            (True, False): "FP",
            (False, True): "FN",
            (False, False): "TN",
        }
        for values, outcome in expected.items():
            with self.subTest(predicted=values[0], observed=values[1]):
                self.assertEqual(classify_outcome(*values), outcome)

    def test_global_summary_aggregates_only_validated_captures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = CaptureRepository(Path(temp_dir) / "captures")
            first = CaptureOrchestrator(repository).simulate(
                repository.create("Acierto", kind="human").capture_id
            )
            second = CaptureOrchestrator(repository).simulate(
                repository.create("Falso positivo", kind="baseline").capture_id
            )
            repository.create("Sin validar", kind="human")
            record_validation(first, True)
            record_validation(second, False)

            summary = summarize_repository(repository)

            self.assertEqual(summary["overall"]["total"], 2)
            self.assertEqual(summary["overall"]["TP"], 1)
            self.assertEqual(summary["overall"]["FP"], 1)
            self.assertEqual(summary["overall"]["accuracy_percent"], 50.0)
            self.assertEqual(summary["unvalidated_captures"], 1)
            self.assertEqual(summary["by_kind"]["human"]["TP"], 1)


if __name__ == "__main__":
    unittest.main()
