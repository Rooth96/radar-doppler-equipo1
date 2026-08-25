import json
from pathlib import Path

import pandas as pd

from data_loader import (
    load_sdr_config,
    load_detection_config,
    load_spectrum,
    load_waterfall,
)

from detection import detect_movement

from metrics import (
    calculate_wavelength_m,
    estimate_velocity_kmh,
)


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

DETECTION_OUTPUT_PATH = (
    PROCESSED_DIR
    / "detection_latest.json"
)

EVENTS_OUTPUT_PATH = (
    PROCESSED_DIR
    / "events.csv"
)

METRICS_OUTPUT_PATH = (
    PROCESSED_DIR
    / "metrics.json"
)


# ============================================================
# ASEGURAR CARPETA DE SALIDA
# ============================================================

def ensure_processed_directory():
    """
    Crea data/processed si no existe.
    """

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# GENERAR detection_latest.json
# ============================================================

def write_detection_latest(
    timestamp,
    detected,
    doppler_hz,
    snr_db,
    velocity_est_kmh,
):
    """
    Genera detection_latest.json respetando
    el contrato Python -> Streamlit.
    """

    output = {
        "timestamp": str(timestamp),

        "detected": bool(
            detected
        ),

        "doppler_hz": round(
            float(doppler_hz),
            2
        ),

        "snr_db": round(
            float(snr_db),
            2
        ),

        "velocity_est_kmh": round(
            float(velocity_est_kmh),
            2
        ),
    }

    with open(
        DETECTION_OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )

    return output


# ============================================================
# GENERAR / ACTUALIZAR events.csv
# ============================================================

def write_event(
    timestamp,
    doppler_hz,
    snr_db,
    peak_power_db,
    noise_floor_db,
    velocity_est_kmh,
    detected,
):
    """
    Registra el resultado de la captura
    en events.csv.

    Si existe el mismo timestamp,
    reemplaza la fila para evitar duplicados.
    """

    new_event = {
        "timestamp": str(timestamp),

        "doppler_hz": round(
            float(doppler_hz),
            2
        ),

        "snr_db": round(
            float(snr_db),
            2
        ),

        "peak_power_db": round(
            float(peak_power_db),
            2
        ),

        "noise_floor_db": round(
            float(noise_floor_db),
            2
        ),

        "velocity_est_kmh": round(
            float(velocity_est_kmh),
            2
        ),

        "detected": bool(
            detected
        ),
    }

    new_dataframe = pd.DataFrame(
        [new_event]
    )

    if EVENTS_OUTPUT_PATH.exists():

        events = pd.read_csv(
            EVENTS_OUTPUT_PATH
        )

        events = events[
            events["timestamp"].astype(str)
            != str(timestamp)
        ]

        events = pd.concat(
            [
                events,
                new_dataframe
            ],
            ignore_index=True
        )

    else:

        events = new_dataframe

    events.to_csv(
        EVENTS_OUTPUT_PATH,
        index=False,
        encoding="utf-8"
    )

    return new_event


# ============================================================
# GENERAR metrics.json
# ============================================================

def write_metrics(
    timestamp,
    current_doppler_hz,
    current_snr_db,
    current_velocity_est_kmh,
    movement_detected,
    carrier_attenuation_db=0.0,
    true_positives=0,
    false_positives=0,
    false_negatives=0,
):
    """
    Genera metrics.json para Streamlit.

    Los indicadores de efectividad experimental
    permanecen en cero mientras no exista una
    serie de pruebas etiquetadas con verdad terreno.
    """

    if EVENTS_OUTPUT_PATH.exists():

        events = pd.read_csv(
            EVENTS_OUTPUT_PATH
        )

    else:

        events = pd.DataFrame()

    # --------------------------------------------------------
    # TOTAL DE EVENTOS POSITIVOS
    # --------------------------------------------------------

    if (
        not events.empty
        and "detected" in events.columns
    ):

        detected_column = (
            events["detected"]
            .astype(str)
            .str.lower()
        )

        total_events = int(
            (
                detected_column
                == "true"
            ).sum()
        )

    else:

        total_events = 0

    # --------------------------------------------------------
    # SNR PROMEDIO
    # --------------------------------------------------------

    if (
        not events.empty
        and "snr_db" in events.columns
    ):

        average_snr_db = float(
            events[
                "snr_db"
            ].mean()
        )

    else:

        average_snr_db = 0.0

    # --------------------------------------------------------
    # DOPPLER MAXIMO ABSOLUTO
    # --------------------------------------------------------

    if (
        not events.empty
        and "doppler_hz" in events.columns
    ):

        max_doppler_hz = float(
            events[
                "doppler_hz"
            ].abs().max()
        )

    else:

        max_doppler_hz = 0.0

    # --------------------------------------------------------
    # TASA DE DETECCION
    # --------------------------------------------------------

    confirmed_cases = (
        true_positives
        + false_negatives
    )

    if confirmed_cases > 0:

        detection_rate_percent = (
            true_positives
            / confirmed_cases
            * 100.0
        )

    else:

        detection_rate_percent = 0.0

    # --------------------------------------------------------
    # TASA DE FALSOS POSITIVOS
    # --------------------------------------------------------

    positive_detections = (
        true_positives
        + false_positives
    )

    if positive_detections > 0:

        false_positive_rate_percent = (
            false_positives
            / positive_detections
            * 100.0
        )

    else:

        false_positive_rate_percent = 0.0

    # --------------------------------------------------------
    # ESTRUCTURA FINAL
    # --------------------------------------------------------

    metrics = {
        "timestamp": str(
            timestamp
        ),

        "current_doppler_hz": round(
            float(current_doppler_hz),
            2
        ),

        "current_snr_db": round(
            float(current_snr_db),
            2
        ),

        "current_velocity_est_kmh": round(
            float(current_velocity_est_kmh),
            2
        ),

        "movement_detected": bool(
            movement_detected
        ),

        "carrier_attenuation_db": round(
            float(carrier_attenuation_db),
            2
        ),

        "total_events": int(
            total_events
        ),

        "true_positives": int(
            true_positives
        ),

        "false_positives": int(
            false_positives
        ),

        "false_negatives": int(
            false_negatives
        ),

        "detection_rate_percent": round(
            float(detection_rate_percent),
            2
        ),

        "false_positive_rate_percent": round(
            float(false_positive_rate_percent),
            2
        ),

        "average_snr_db": round(
            float(average_snr_db),
            2
        ),

        "max_doppler_hz": round(
            float(max_doppler_hz),
            2
        ),
    }

    with open(
        METRICS_OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metrics,
            file,
            indent=2,
            ensure_ascii=False
        )

    return metrics


# ============================================================
# EJECUCION PRINCIPAL
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # 0. PREPARAR CARPETA
    # --------------------------------------------------------

    ensure_processed_directory()

    # --------------------------------------------------------
    # 1. LEER ENTRADAS
    # --------------------------------------------------------

    sdr_config = (
        load_sdr_config()
    )

    detection_config = (
        load_detection_config()
    )

    spectrum = (
        load_spectrum()
    )

    waterfall = (
        load_waterfall()
    )

    # --------------------------------------------------------
    # 2. PARAMETROS DEL DETECTOR
    # --------------------------------------------------------

    exclusion_hz = float(
        detection_config[
            "exclusion_hz"
        ]
    )

    reference_notch_hz = float(
        detection_config[
            "reference_notch_hz"
        ]
    )

    min_doppler_hz = float(
        detection_config[
            "min_doppler_hz"
        ]
    )

    max_doppler_hz = float(
        detection_config[
            "max_doppler_hz"
        ]
    )

    threshold_db = float(
        detection_config[
            "threshold_db"
        ]
    )

    minimum_hits = int(
        detection_config[
            "minimum_hits"
        ]
    )

    geometry_factor = float(
        detection_config[
            "geometry_factor"
        ]
    )

    # --------------------------------------------------------
    # 3. EJECUTAR DETECTOR CALIBRADO
    # --------------------------------------------------------

    result = detect_movement(
        spectrum=spectrum,
        waterfall=waterfall,

        exclusion_hz=(
            exclusion_hz
        ),

        threshold_db=(
            threshold_db
        ),

        minimum_hits=(
            minimum_hits
        ),

        reference_notch_hz=(
            reference_notch_hz
        ),

        min_doppler_hz=(
            min_doppler_hz
        ),

        max_doppler_hz=(
            max_doppler_hz
        ),
    )

    # --------------------------------------------------------
    # 4. CALCULAR LONGITUD DE ONDA
    # --------------------------------------------------------

    wavelength_m = (
        calculate_wavelength_m(
            sdr_config[
                "center_frequency_hz"
            ]
        )
    )

    # --------------------------------------------------------
    # 5. ESTIMAR VELOCIDAD
    # --------------------------------------------------------

    if result["detected"]:

        velocity_est_kmh = (
            estimate_velocity_kmh(
                doppler_hz=(
                    result[
                        "doppler_hz"
                    ]
                ),

                wavelength_m=(
                    wavelength_m
                ),

                geometry_factor=(
                    geometry_factor
                ),
            )
        )

    else:

        velocity_est_kmh = 0.0

    # --------------------------------------------------------
    # 6. TIMESTAMP DE LA CAPTURA
    # --------------------------------------------------------

    timestamp = str(
        spectrum[
            "timestamp"
        ].iloc[-1]
    )

    # --------------------------------------------------------
    # 7. detection_latest.json
    # --------------------------------------------------------

    detection_output = (
        write_detection_latest(
            timestamp=timestamp,

            detected=(
                result[
                    "detected"
                ]
            ),

            doppler_hz=(
                result[
                    "doppler_hz"
                ]
            ),

            snr_db=(
                result[
                    "snr_db"
                ]
            ),

            velocity_est_kmh=(
                velocity_est_kmh
            ),
        )
    )

    # --------------------------------------------------------
    # 8. events.csv
    # --------------------------------------------------------

    event_output = (
        write_event(
            timestamp=timestamp,

            doppler_hz=(
                result[
                    "doppler_hz"
                ]
            ),

            snr_db=(
                result[
                    "snr_db"
                ]
            ),

            peak_power_db=(
                result[
                    "peak_power_db"
                ]
            ),

            noise_floor_db=(
                result[
                    "noise_floor_db"
                ]
            ),

            velocity_est_kmh=(
                velocity_est_kmh
            ),

            detected=(
                result[
                    "detected"
                ]
            ),
        )
    )

    # --------------------------------------------------------
    # 9. metrics.json
    # --------------------------------------------------------

    metrics_output = (
        write_metrics(
            timestamp=timestamp,

            current_doppler_hz=(
                result[
                    "doppler_hz"
                ]
            ),

            current_snr_db=(
                result[
                    "snr_db"
                ]
            ),

            current_velocity_est_kmh=(
                velocity_est_kmh
            ),

            movement_detected=(
                result[
                    "detected"
                ]
            ),

            # Pendiente de medicion fisica.
            carrier_attenuation_db=0.0,

            # Pendientes de una serie experimental.
            true_positives=0,
            false_positives=0,
            false_negatives=0,
        )
    )

    # ========================================================
    # RESULTADOS
    # ========================================================

    print(
        "PROCESAMIENTO COMPLETADO CORRECTAMENTE"
    )

    print(
        "------------------------------------"
    )

    print()

    print(
        "CASO ANALIZADO"
    )

    print(
        "-------------"
    )

    print(
        "Captura real GNU Radio / RTL-SDR"
    )

    print()

    print(
        "PARAMETROS UTILIZADOS"
    )

    print(
        "---------------------"
    )

    print(
        f"Notch referencia: "
        f"{reference_notch_hz:.2f} Hz"
    )

    print(
        f"Rango Doppler: "
        f"{min_doppler_hz:.2f} - "
        f"{max_doppler_hz:.2f} Hz"
    )

    print(
        f"Umbral: "
        f"{threshold_db:.2f} dB"
    )

    print(
        f"Persistencia minima: "
        f"{minimum_hits} hits"
    )

    print(
        f"Factor geometrico: "
        f"{geometry_factor:.2f}"
    )

    print(
        f"Estado configuracion: "
        f"{detection_config['status']}"
    )

    print()

    print(
        "RESULTADO DEL DETECTOR"
    )

    print(
        "----------------------"
    )

    print(
        f"Detected: "
        f"{result['detected']}"
    )

    print(
        f"Referencia: "
        f"{result['reference_offset_hz']:.2f} Hz"
    )

    print(
        f"Candidato: "
        f"{result['candidate_frequency_hz']:.2f} Hz"
    )

    print(
        f"Doppler: "
        f"{result['doppler_hz']:.2f} Hz"
    )

    print(
        f"Piso de ruido: "
        f"{result['noise_floor_db']:.2f} dB"
    )

    print(
        f"Potencia candidato: "
        f"{result['peak_power_db']:.2f} dB"
    )

    print(
        f"SNR: "
        f"{result['snr_db']:.2f} dB"
    )

    print(
        f"Velocidad estimada: "
        f"{velocity_est_kmh:.2f} km/h"
    )

    print(
        f"Persistencia: "
        f"{result['persistence_hits']} / "
        f"{result['total_instants']}"
    )

    print()

    print(
        "ARCHIVOS GENERADOS PARA STREAMLIT"
    )

    print(
        "--------------------------------"
    )

    print(
        f"1. {DETECTION_OUTPUT_PATH}"
    )

    print(
        f"2. {EVENTS_OUTPUT_PATH}"
    )

    print(
        f"3. {METRICS_OUTPUT_PATH}"
    )