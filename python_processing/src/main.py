import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from data_loader import load_detection_config


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_WRITER_PATH = (
    CURRENT_DIR
    / "output_writer.py"
)

SPECTRUM_PATH = (
    PROJECT_ROOT
    / "data"
    / "realtime"
    / "spectrum_latest.csv"
)


# ============================================================
# OBTENER TIMESTAMP DEL ESPECTRO ACTUAL
# ============================================================

def get_current_spectrum_timestamp():
    """
    Lee spectrum_latest.csv y obtiene el timestamp
    correspondiente a la captura disponible.

    Retorna None si el archivo no existe,
    esta vacio o no puede ser leido.
    """

    if not SPECTRUM_PATH.exists():

        return None

    try:

        spectrum = pd.read_csv(
            SPECTRUM_PATH
        )

        if spectrum.empty:

            return None

        if "timestamp" not in spectrum.columns:

            return None

        timestamp = str(
            spectrum[
                "timestamp"
            ].iloc[-1]
        )

        return timestamp

    except Exception as error:

        print(
            "Error leyendo "
            "spectrum_latest.csv:"
        )

        print(
            error
        )

        return None


# ============================================================
# EJECUTAR UN CICLO DE PROCESAMIENTO
# ============================================================

def run_processing_cycle():
    """
    Ejecuta output_writer.py una sola vez.

    output_writer.py realiza el procesamiento
    y actualiza:

    - detection_latest.json
    - events.csv
    - metrics.json
    """

    result = subprocess.run(
        [
            sys.executable,
            str(OUTPUT_WRITER_PATH)
        ],
        check=False
    )

    return result.returncode


# ============================================================
# MODO CONTINUO
# ============================================================

def run_continuous():
    """
    Ejecuta continuamente el modulo Python.

    Solo procesa cuando spectrum_latest.csv
    contiene un timestamp diferente al ultimo
    timestamp procesado.
    """

    # --------------------------------------------------------
    # 1. Leer configuracion del detector
    # --------------------------------------------------------

    detection_config = (
        load_detection_config()
    )

    poll_interval_seconds = float(
        detection_config[
            "poll_interval_seconds"
        ]
    )

    config_status = str(
        detection_config[
            "status"
        ]
    )

    # --------------------------------------------------------
    # 2. Mostrar inicio
    # --------------------------------------------------------

    print()
    print(
        "=========================================="
    )

    print(
        " RADAR DOPPLER PASIVO - MODULO PYTHON"
    )

    print(
        "=========================================="
    )

    print()

    print(
        "Modo continuo iniciado."
    )

    print(
        f"Intervalo de revision: "
        f"{poll_interval_seconds:.2f} s"
    )

    print(
        f"Estado configuracion: "
        f"{config_status}"
    )

    print()

    print(
        "Esperando datos nuevos de GNU Radio..."
    )

    print(
        "Presione Ctrl+C para detener."
    )

    print()

    # --------------------------------------------------------
    # 3. Timestamp de control
    # --------------------------------------------------------

    last_processed_timestamp = None

    # --------------------------------------------------------
    # 4. Ciclo continuo
    # --------------------------------------------------------

    try:

        while True:

            current_timestamp = (
                get_current_spectrum_timestamp()
            )

            # ------------------------------------------------
            # No hay datos disponibles
            # ------------------------------------------------

            if current_timestamp is None:

                time.sleep(
                    poll_interval_seconds
                )

                continue

            # ------------------------------------------------
            # Existe una captura nueva
            # ------------------------------------------------

            if (
                current_timestamp
                != last_processed_timestamp
            ):

                print()
                print(
                    "Nueva captura detectada:"
                )

                print(
                    current_timestamp
                )

                print(
                    "Procesando..."
                )

                # --------------------------------------------
                # Ejecutar procesamiento completo
                # --------------------------------------------

                return_code = (
                    run_processing_cycle()
                )

                # --------------------------------------------
                # Procesamiento correcto
                # --------------------------------------------

                if return_code == 0:

                    last_processed_timestamp = (
                        current_timestamp
                    )

                    print()
                    print(
                        "Captura procesada "
                        "correctamente."
                    )

                    print(
                        "Esperando siguiente "
                        "captura..."
                    )

                # --------------------------------------------
                # Error
                # --------------------------------------------

                else:

                    print()
                    print(
                        "ERROR durante el "
                        "procesamiento."
                    )

                    print(
                        f"Codigo de salida: "
                        f"{return_code}"
                    )

            # ------------------------------------------------
            # Esperar antes de revisar nuevamente
            # ------------------------------------------------

            time.sleep(
                poll_interval_seconds
            )

    # --------------------------------------------------------
    # Ctrl + C
    # --------------------------------------------------------

    except KeyboardInterrupt:

        print()
        print()

        print(
            "MODULO PYTHON DETENIDO POR EL USUARIO"
        )

        print(
            "Cierre controlado."
        )


# ============================================================
# EJECUCION PRINCIPAL
# ============================================================

if __name__ == "__main__":

    run_continuous()