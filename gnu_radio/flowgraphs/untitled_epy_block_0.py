"""
Exportador espectral GNU Radio -> Python
Equipo 1 - Radar Doppler Pasivo Monocanal

Este bloque recibe muestras IQ complejas desde el
Frequency Xlating FIR Filter y genera:

- data/realtime/spectrum_latest.csv
- data/realtime/waterfall.csv

Formato de ambos CSV:
timestamp,frequency_offset_hz,power_db
"""

import os
import time
from pathlib import Path
from datetime import datetime
from collections import deque

import numpy as np
from gnuradio import gr


class blk(gr.sync_block):

    def __init__(
        self,
        sample_rate=240000.0,
        fft_size=32768,
        update_period=1.0,
        history_seconds=30.0,
        export_half_span_hz=5000.0
    ):

        gr.sync_block.__init__(
            self,
            name="Spectral CSV Exporter",
            in_sig=[np.complex64],
            out_sig=None
        )

        # -----------------------------------------------------
        # PARAMETROS
        # -----------------------------------------------------

        self.sample_rate = float(sample_rate)
        self.fft_size = int(fft_size)
        self.update_period = float(update_period)
        self.history_seconds = float(history_seconds)
        self.export_half_span_hz = float(export_half_span_hz)

        # -----------------------------------------------------
        # VALIDACIONES
        # -----------------------------------------------------

        if self.sample_rate <= 0:
            raise ValueError("sample_rate debe ser mayor que 0")

        if self.fft_size < 32:
            raise ValueError("fft_size debe ser >= 32")

        if self.update_period <= 0:
            raise ValueError("update_period debe ser mayor que 0")

        if self.history_seconds <= 0:
            raise ValueError("history_seconds debe ser mayor que 0")

        if self.export_half_span_hz <= 0:
            raise ValueError("export_half_span_hz debe ser mayor que 0")

        if self.export_half_span_hz > self.sample_rate / 2:
            raise ValueError(
                "export_half_span_hz no puede superar Nyquist"
            )

        # -----------------------------------------------------
        # BUFFER DE MUESTRAS
        # -----------------------------------------------------

        self.sample_buffer = np.empty(
            0,
            dtype=np.complex64
        )

        self.last_update = 0.0

        # -----------------------------------------------------
        # HISTORIAL DEL WATERFALL
        # -----------------------------------------------------

        max_frames = max(
            1,
            int(
                self.history_seconds
                / self.update_period
            )
        )

        self.waterfall_history = deque(
            maxlen=max_frames
        )

        # -----------------------------------------------------
        # RUTAS
        #
        # NO usamos __file__ porque Embedded Python Block
        # puede ejecutarse sin que esa variable exista.
        # -----------------------------------------------------

        self.paths_initialized = False
        self.path_error_reported = False

        self.repo_root = None
        self.realtime_dir = None
        self.spectrum_path = None
        self.waterfall_path = None

        # -----------------------------------------------------
        # VENTANA BLACKMAN-HARRIS
        # 4 TERMINOS
        # -----------------------------------------------------

        n = np.arange(
            self.fft_size,
            dtype=np.float64
        )

        a0 = 0.35875
        a1 = 0.48829
        a2 = 0.14128
        a3 = 0.01168

        self.window = (
            a0
            - a1 * np.cos(
                2.0
                * np.pi
                * n
                / (self.fft_size - 1)
            )
            + a2 * np.cos(
                4.0
                * np.pi
                * n
                / (self.fft_size - 1)
            )
            - a3 * np.cos(
                6.0
                * np.pi
                * n
                / (self.fft_size - 1)
            )
        ).astype(np.float32)

        # -----------------------------------------------------
        # EJE DE FRECUENCIA
        # -----------------------------------------------------

        freqs = np.fft.fftshift(
            np.fft.fftfreq(
                self.fft_size,
                d=1.0 / self.sample_rate
            )
        )

        # Exportar solamente la zona espectral
        # de interés para Doppler.
        #
        # Inicialmente: -5000 Hz ... +5000 Hz
        self.export_mask = (
            np.abs(freqs)
            <= self.export_half_span_hz
        )

        self.export_freqs = freqs[
            self.export_mask
        ]

        # -----------------------------------------------------
        # INFORMACION DE INICIO
        # -----------------------------------------------------

        print("")
        print(
            "=========================================="
        )
        print(
            "Spectral CSV Exporter inicializado"
        )
        print(
            "=========================================="
        )
        print(
            "Sample rate:",
            self.sample_rate,
            "Hz"
        )
        print(
            "FFT size:",
            self.fft_size
        )
        print(
            "Resolucion:",
            self.sample_rate / self.fft_size,
            "Hz/bin"
        )
        print(
            "Rango exportado:",
            -self.export_half_span_hz,
            "a",
            self.export_half_span_hz,
            "Hz"
        )
        print(
            "Actualizacion:",
            self.update_period,
            "s"
        )
        print(
            "Historial waterfall:",
            self.history_seconds,
            "s"
        )
        print(
            "=========================================="
        )
        print("")


    # =========================================================
    # LOCALIZAR REPOSITORIO
    # =========================================================

    def _find_repo_root(self):

        candidates = []

        # Directorio desde donde se ejecuta GNU Radio
        cwd = Path.cwd().resolve()

        candidates.append(cwd)

        for parent in cwd.parents:
            candidates.append(parent)

        # Rutas habituales en Windows
        home = Path.home()

        candidates.extend([
            home
            / "OneDrive"
            / "Escritorio"
            / "radar-doppler-equipo1",

            home
            / "Desktop"
            / "radar-doppler-equipo1",

            home
            / "Escritorio"
            / "radar-doppler-equipo1",

            home
            / "OneDrive"
            / "Desktop"
            / "radar-doppler-equipo1",
        ])

        # Eliminar duplicados
        unique_candidates = []

        for candidate in candidates:

            candidate = candidate.resolve()

            if candidate not in unique_candidates:
                unique_candidates.append(
                    candidate
                )

        # Buscar estructura esperada
        for candidate in unique_candidates:

            try:

                if (
                    (candidate / "gnu_radio").exists()
                    and
                    (candidate / "data").exists()
                    and
                    (candidate / "config").exists()
                ):

                    return candidate

            except Exception:
                pass

        return None


    # =========================================================
    # PREPARAR RUTAS
    # =========================================================

    def _ensure_paths(self):

        if self.paths_initialized:
            return True

        repo_root = self._find_repo_root()

        if repo_root is None:

            if not self.path_error_reported:

                print("")
                print(
                    "ERROR: Spectral CSV Exporter"
                )
                print(
                    "No se pudo localizar el repositorio:"
                )
                print(
                    "radar-doppler-equipo1"
                )
                print("")
                print(
                    "Ruta actual:"
                )
                print(
                    Path.cwd().resolve()
                )
                print("")

                self.path_error_reported = True

            return False

        self.repo_root = repo_root

        self.realtime_dir = (
            self.repo_root
            / "data"
            / "realtime"
        )

        self.realtime_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.spectrum_path = (
            self.realtime_dir
            / "spectrum_latest.csv"
        )

        self.waterfall_path = (
            self.realtime_dir
            / "waterfall.csv"
        )

        self.paths_initialized = True

        print("")
        print(
            "Repositorio detectado:"
        )
        print(
            self.repo_root
        )
        print("")
        print(
            "Spectrum CSV:"
        )
        print(
            self.spectrum_path
        )
        print("")
        print(
            "Waterfall CSV:"
        )
        print(
            self.waterfall_path
        )
        print("")

        return True


    # =========================================================
    # CALCULAR ESPECTRO
    # =========================================================

    def _calculate_spectrum(self):

        # Usar las muestras más recientes
        frame = self.sample_buffer[
            -self.fft_size:
        ]

        # Aplicar ventana Blackman-Harris
        windowed = (
            frame
            * self.window
        )

        # FFT
        spectrum = np.fft.fft(
            windowed,
            n=self.fft_size
        )

        spectrum = np.fft.fftshift(
            spectrum
        )

        # Potencia espectral relativa
        power = (
            np.abs(spectrum) ** 2
        )

        normalization = (
            np.sum(
                self.window ** 2
            )
            + 1e-20
        )

        power = (
            power
            / normalization
        )

        # Convertir a dB
        power_db = (
            10.0
            * np.log10(
                power + 1e-20
            )
        )

        # Solamente zona de interés
        return power_db[
            self.export_mask
        ]


    # =========================================================
    # ESCRIBIR spectrum_latest.csv
    # =========================================================

    def _write_spectrum(
        self,
        timestamp,
        power_db
    ):

        temp_path = (
            self.spectrum_path.parent
            / (
                self.spectrum_path.name
                + ".tmp"
            )
        )

        with open(
            temp_path,
            "w",
            encoding="utf-8",
            newline=""
        ) as f:

            f.write(
                "timestamp,"
                "frequency_offset_hz,"
                "power_db\n"
            )

            for freq, power in zip(
                self.export_freqs,
                power_db
            ):

                f.write(
                    f"{timestamp},"
                    f"{freq:.6f},"
                    f"{power:.6f}\n"
                )

        # Reemplazo atomico:
        # evita que Python lea un archivo
        # mientras todavía se está escribiendo.
        os.replace(
            temp_path,
            self.spectrum_path
        )


    # =========================================================
    # ESCRIBIR waterfall.csv
    # =========================================================

    def _write_waterfall(self):

        temp_path = (
            self.waterfall_path.parent
            / (
                self.waterfall_path.name
                + ".tmp"
            )
        )

        with open(
            temp_path,
            "w",
            encoding="utf-8",
            newline=""
        ) as f:

            f.write(
                "timestamp,"
                "frequency_offset_hz,"
                "power_db\n"
            )

            for (
                timestamp,
                power_db
            ) in self.waterfall_history:

                for freq, power in zip(
                    self.export_freqs,
                    power_db
                ):

                    f.write(
                        f"{timestamp},"
                        f"{freq:.6f},"
                        f"{power:.6f}\n"
                    )

        os.replace(
            temp_path,
            self.waterfall_path
        )


    # =========================================================
    # WORK
    # =========================================================

    def work(
        self,
        input_items,
        output_items
    ):

        samples = input_items[0]

        number_samples = len(samples)

        if number_samples == 0:
            return 0

        # -----------------------------------------------------
        # AGREGAR NUEVAS MUESTRAS
        # -----------------------------------------------------

        self.sample_buffer = np.concatenate(
            (
                self.sample_buffer,
                samples
            )
        )

        # Mantener solamente una FFT
        # de muestras recientes.
        if (
            len(self.sample_buffer)
            > self.fft_size
        ):

            self.sample_buffer = (
                self.sample_buffer[
                    -self.fft_size:
                ]
            )

        # -----------------------------------------------------
        # ESPERAR FFT COMPLETA
        # -----------------------------------------------------

        if (
            len(self.sample_buffer)
            < self.fft_size
        ):

            return number_samples

        # -----------------------------------------------------
        # CONTROL DE ACTUALIZACION
        # -----------------------------------------------------

        now = time.time()

        if (
            now - self.last_update
            < self.update_period
        ):

            return number_samples

        # -----------------------------------------------------
        # LOCALIZAR CARPETAS
        # -----------------------------------------------------

        if not self._ensure_paths():

            return number_samples

        # -----------------------------------------------------
        # TIMESTAMP ISO 8601
        # -----------------------------------------------------

        timestamp = (
            datetime
            .now()
            .astimezone()
            .isoformat(
                timespec="milliseconds"
            )
        )

        # -----------------------------------------------------
        # CALCULAR FFT
        # -----------------------------------------------------

        power_db = (
            self._calculate_spectrum()
        )

        # -----------------------------------------------------
        # spectrum_latest.csv
        # -----------------------------------------------------

        self._write_spectrum(
            timestamp,
            power_db
        )

        # -----------------------------------------------------
        # WATERFALL
        # -----------------------------------------------------

        self.waterfall_history.append(
            (
                timestamp,
                power_db.copy()
            )
        )

        self._write_waterfall()

        # -----------------------------------------------------
        # ACTUALIZAR TIEMPO
        # -----------------------------------------------------

        self.last_update = now

        return number_samples