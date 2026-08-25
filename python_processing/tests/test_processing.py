import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


# ============================================================
# PERMITIR IMPORTAR LOS MODULOS DE src
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = (
    PROJECT_ROOT
    / "python_processing"
    / "src"
)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR)
    )


# ============================================================
# IMPORTACIONES DEL MODULO PYTHON
# ============================================================

import data_loader

from signal_processing import (
    estimate_noise_floor,
    find_reference_carrier,
    suppress_reference_notch,
    find_doppler_candidate,
)

from metrics import (
    calculate_doppler_hz,
    calculate_snr_db,
    calculate_wavelength_m,
    estimate_velocity_kmh,
)

from detection import (
    detect_movement,
)


# ============================================================
# CLASE DE PRUEBAS
# ============================================================

class TestRadarDopplerProcessing(
    unittest.TestCase
):

    # ========================================================
    # DATOS SINTETICOS DE PRUEBA
    # ========================================================

    def setUp(self):
        """
        Genera datos sinteticos controlados.

        Estos datos NO dependen de GNU Radio
        ni de archivos reales del repositorio.
        """

        # ----------------------------------------------------
        # Espectro con:
        #
        # - portadora en 0 Hz
        # - candidato Doppler en +100 Hz
        # - ruido alrededor de -69 dB
        # ----------------------------------------------------

        self.spectrum = pd.DataFrame(
            {
                "timestamp": [
                    "2026-08-25T14:30:01.000"
                ] * 9,

                "frequency_offset_hz": [
                    -200,
                    -150,
                    -100,
                    -50,
                    0,
                    50,
                    100,
                    150,
                    200,
                ],

                "power_db": [
                    -70.5,
                    -69.8,
                    -68.7,
                    -62.5,
                    -25.4,
                    -63.1,
                    -52.0,
                    -68.9,
                    -70.1,
                ],
            }
        )

        # ----------------------------------------------------
        # Waterfall con candidato persistente en +100 Hz
        # durante 3 instantes.
        # ----------------------------------------------------

        self.waterfall = pd.DataFrame(
            {
                "timestamp": [
                    "2026-08-25T14:30:01.000",
                    "2026-08-25T14:30:01.000",
                    "2026-08-25T14:30:01.000",
                    "2026-08-25T14:30:01.000",
                    "2026-08-25T14:30:01.000",

                    "2026-08-25T14:30:02.000",
                    "2026-08-25T14:30:02.000",
                    "2026-08-25T14:30:02.000",
                    "2026-08-25T14:30:02.000",
                    "2026-08-25T14:30:02.000",

                    "2026-08-25T14:30:03.000",
                    "2026-08-25T14:30:03.000",
                    "2026-08-25T14:30:03.000",
                    "2026-08-25T14:30:03.000",
                    "2026-08-25T14:30:03.000",
                ],

                "frequency_offset_hz": [
                    -200,
                    -100,
                    0,
                    100,
                    200,

                    -200,
                    -100,
                    0,
                    100,
                    200,

                    -200,
                    -100,
                    0,
                    100,
                    200,
                ],

                "power_db": [
                    -70.5,
                    -68.7,
                    -25.4,
                    -52.0,
                    -70.1,

                    -70.2,
                    -68.4,
                    -25.3,
                    -50.8,
                    -69.9,

                    -70.6,
                    -68.9,
                    -25.5,
                    -51.3,
                    -70.0,
                ],
            }
        )

    # ========================================================
    # TEST 1
    # CONFIGURACION SDR
    # ========================================================

    def test_sdr_config(self):

        test_config = {
            "timestamp":
                "2026-08-25T14:30:00",

            "center_frequency_hz":
                99700000,

            "sample_rate_hz":
                2048000,

            "gain_db":
                28.0,

            "fft_size":
                65536,

            "frequency_resolution_hz":
                31.25,

            "window_type":
                "hann",

            "source_device":
                "RTL-SDR EQ-2",
        }

        with tempfile.TemporaryDirectory() as temp_dir:

            temp_path = (
                Path(temp_dir)
                / "sdr_config.json"
            )

            with open(
                temp_path,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    test_config,
                    file
                )

            with patch.object(
                data_loader,
                "SDR_CONFIG_PATH",
                temp_path
            ):

                loaded = (
                    data_loader
                    .load_sdr_config()
                )

        self.assertEqual(
            loaded[
                "center_frequency_hz"
            ],
            99700000
        )

        self.assertEqual(
            loaded[
                "fft_size"
            ],
            65536
        )

        self.assertEqual(
            loaded[
                "source_device"
            ],
            "RTL-SDR EQ-2"
        )

    # ========================================================
    # TEST 2
    # PISO DE RUIDO
    # ========================================================

    def test_noise_floor(self):

        noise_floor = (
            estimate_noise_floor(
                self.spectrum,
                central_exclusion_hz=50.0
            )
        )

        self.assertAlmostEqual(
            noise_floor,
            -69.35,
            places=2
        )

    # ========================================================
    # TEST 3
    # PORTADORA / REFERENCIA
    # ========================================================

    def test_reference_carrier(self):

        (
            reference_frequency,
            reference_power
        ) = find_reference_carrier(
            self.spectrum,
            search_range_hz=50.0
        )

        self.assertAlmostEqual(
            reference_frequency,
            0.0,
            places=2
        )

        self.assertAlmostEqual(
            reference_power,
            -25.4,
            places=2
        )

    # ========================================================
    # TEST 4
    # SUPRESION DE REFERENCIA
    # ========================================================

    def test_reference_suppression(self):

        noise_floor = (
            estimate_noise_floor(
                self.spectrum,
                central_exclusion_hz=50.0
            )
        )

        (
            reference_frequency,
            _
        ) = find_reference_carrier(
            self.spectrum,
            search_range_hz=50.0
        )

        suppressed = (
            suppress_reference_notch(
                spectrum=self.spectrum,
                reference_offset_hz=(
                    reference_frequency
                ),
                noise_floor_db=noise_floor,
                notch_half_width_hz=50.0,
            )
        )

        reference_row = suppressed[
            suppressed[
                "frequency_offset_hz"
            ] == 0
        ]

        reference_after = float(
            reference_row[
                "power_suppressed_db"
            ].iloc[0]
        )

        self.assertAlmostEqual(
            reference_after,
            noise_floor,
            places=2
        )

        candidate_row = suppressed[
            suppressed[
                "frequency_offset_hz"
            ] == 100
        ]

        candidate_after = float(
            candidate_row[
                "power_suppressed_db"
            ].iloc[0]
        )

        self.assertAlmostEqual(
            candidate_after,
            -52.0,
            places=2
        )

    # ========================================================
    # TEST 5
    # CANDIDATO DOPPLER
    # ========================================================

    def test_doppler_candidate(self):

        noise_floor = (
            estimate_noise_floor(
                self.spectrum,
                central_exclusion_hz=50.0
            )
        )

        (
            reference_frequency,
            _
        ) = find_reference_carrier(
            self.spectrum,
            search_range_hz=50.0
        )

        suppressed = (
            suppress_reference_notch(
                spectrum=self.spectrum,
                reference_offset_hz=(
                    reference_frequency
                ),
                noise_floor_db=noise_floor,
                notch_half_width_hz=50.0,
            )
        )

        candidate = (
            find_doppler_candidate(
                spectrum=suppressed,
                reference_offset_hz=(
                    reference_frequency
                ),
                noise_floor_db=noise_floor,
                exclusion_hz=50.0,
                threshold_db=8.0,
                power_column=(
                    "power_suppressed_db"
                ),
            )
        )

        self.assertIsNotNone(
            candidate
        )

        self.assertAlmostEqual(
            candidate[
                "frequency_hz"
            ],
            100.0,
            places=2
        )

        self.assertAlmostEqual(
            candidate[
                "power_db"
            ],
            -52.0,
            places=2
        )

    # ========================================================
    # TEST 6
    # CALCULO DOPPLER
    # ========================================================

    def test_doppler_calculation(self):

        doppler_hz = (
            calculate_doppler_hz(
                100.0,
                0.0
            )
        )

        self.assertAlmostEqual(
            doppler_hz,
            100.0,
            places=2
        )

    # ========================================================
    # TEST 7
    # CALCULO SNR
    # ========================================================

    def test_snr_calculation(self):

        snr_db = (
            calculate_snr_db(
                -52.0,
                -69.35
            )
        )

        self.assertAlmostEqual(
            snr_db,
            17.35,
            places=2
        )

    # ========================================================
    # TEST 8
    # LONGITUD DE ONDA
    # ========================================================

    def test_wavelength(self):

        wavelength = (
            calculate_wavelength_m(
                99700000
            )
        )

        self.assertAlmostEqual(
            wavelength,
            3.0069,
            places=3
        )

    # ========================================================
    # TEST 9
    # VELOCIDAD ESTIMADA
    # ========================================================

    def test_velocity_estimation(self):

        wavelength = (
            calculate_wavelength_m(
                99700000
            )
        )

        velocity_kmh = (
            estimate_velocity_kmh(
                doppler_hz=100.0,
                wavelength_m=wavelength,
                geometry_factor=2.0,
            )
        )

        self.assertAlmostEqual(
            velocity_kmh,
            541.25,
            places=1
        )

    # ========================================================
    # TEST 10
    # DETECCION COMPLETA POSITIVA
    # ========================================================

    def test_complete_detection(self):

        result = detect_movement(
            spectrum=self.spectrum,
            waterfall=self.waterfall,
            exclusion_hz=50.0,
            threshold_db=8.0,
            minimum_hits=2,
        )

        self.assertTrue(
            result[
                "detected"
            ]
        )

        self.assertAlmostEqual(
            result[
                "doppler_hz"
            ],
            100.0,
            places=2
        )

        self.assertAlmostEqual(
            result[
                "snr_db"
            ],
            17.35,
            places=2
        )

        self.assertEqual(
            result[
                "persistence_hits"
            ],
            3
        )

    # ========================================================
    # TEST 11
    # ESCENARIO SIN BLANCO
    # ========================================================

    def test_no_detection_when_no_doppler_peak(self):

        spectrum_without_target = (
            self.spectrum.copy()
        )

        spectrum_without_target.loc[
            spectrum_without_target[
                "frequency_offset_hz"
            ] == 100,
            "power_db"
        ] = -69.0

        waterfall_without_target = (
            self.waterfall.copy()
        )

        waterfall_without_target.loc[
            waterfall_without_target[
                "frequency_offset_hz"
            ] == 100,
            "power_db"
        ] = -69.0

        result = detect_movement(
            spectrum=(
                spectrum_without_target
            ),

            waterfall=(
                waterfall_without_target
            ),

            exclusion_hz=50.0,

            threshold_db=8.0,

            minimum_hits=2,
        )

        self.assertFalse(
            result[
                "detected"
            ]
        )


# ============================================================
# EJECUCION
# ============================================================

if __name__ == "__main__":

    unittest.main()