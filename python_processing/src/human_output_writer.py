from pathlib import Path
import json

import pandas as pd

from human_detection import (
    load_case_data,
    detect_human_movement,
    calculate_equivalent_velocity,
)


# ============================================================
# RUTAS DEL CASO 2
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "archive"
    / "caso_02_con_persona"
)

PROCESSED_DIR = (
    CASE_DIR
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
# CREAR CARPETA PROCESSED
# ============================================================

def ensure_processed_directory():

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# GENERAR detection_latest.json
# ============================================================

def write_detection_latest(
    result,
    velocity_equivalent_kmh,
    detection_config,
):

    detected = bool(
        result["detected"]
    )

    if detected:

        timestamp = str(
            result["event_timestamp"]
        )

        doppler_hz = float(
            result["doppler_hz"]
        )

        excess_db = float(
            result["excess_db"]
        )

        peak_power_db = float(
            result["peak_power_db"]
        )

        baseline_power_db = float(
            result["baseline_power_db"]
        )

        active_bins = int(
            result["active_bins"]
        )

    else:

        timestamp = None
        doppler_hz = 0.0
        excess_db = 0.0
        peak_power_db = 0.0
        baseline_power_db = 0.0
        active_bins = 0

    output = {

        "case_name": (
            detection_config[
                "case_name"
            ]
        ),

        "detection_mode": (
            detection_config[
                "detection_mode"
            ]
        ),

        "timestamp": timestamp,

        "detected": detected,

        "doppler_hz": round(
            doppler_hz,
            3
        ),

        # ----------------------------------------------------
        # COMPATIBILIDAD CON STREAMLIT
        #
        # En este Caso 2, snr_db representa el aumento
        # respecto del baseline de reposo.
        # ----------------------------------------------------

        "snr_db": round(
            excess_db,
            3
        ),

        "snr_definition": (
            "EXCESO_SOBRE_BASELINE_REPOSO_DB"
        ),

        "excess_db": round(
            excess_db,
            3
        ),

        "peak_power_db": round(
            peak_power_db,
            3
        ),

        "baseline_power_db": round(
            baseline_power_db,
            3
        ),

        "velocity_est_kmh": round(
            float(
                velocity_equivalent_kmh
            ),
            2
        ),

        "velocity_definition": (
            "VELOCIDAD_EQUIVALENTE_MODELO_DOPPLER_SIMPLIFICADO"
        ),

        "active_bins": active_bins,

        "minimum_active_bins": int(
            detection_config[
                "minimum_active_bins"
            ]
        ),

        "persistence_hits": int(
            result[
                "event_hits"
            ]
        ),

        "minimum_hits": int(
            detection_config[
                "minimum_hits"
            ]
        ),

        "baseline_instants": int(
            result[
                "baseline_instants"
            ]
        ),

        "total_instants": int(
            result[
                "total_instants"
            ]
        ),

        "rest_start": str(
            result[
                "rest_start"
            ]
        ),

        "rest_end": str(
            result[
                "rest_end"
            ]
        ),

        "ground_truth": (
            detection_config[
                "ground_truth"
            ]
        ),

        "ground_truth_timing": (
            detection_config[
                "ground_truth_timing"
            ]
        ),

        "validation_status": (
            "CORRELACION_TEMPORAL_APROXIMADA"
        ),

        "status": (
            detection_config[
                "status"
            ]
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
# GENERAR events.csv
# ============================================================

def write_events(
    result,
    velocity_equivalent_kmh,
):

    if result["detected"]:

        event = {

            "timestamp": str(
                result[
                    "event_timestamp"
                ]
            ),

            "doppler_hz": round(
                float(
                    result[
                        "doppler_hz"
                    ]
                ),
                3
            ),

            # En este caso corresponde al exceso
            # sobre el baseline de reposo.
            "snr_db": round(
                float(
                    result[
                        "excess_db"
                    ]
                ),
                3
            ),

            "peak_power_db": round(
                float(
                    result[
                        "peak_power_db"
                    ]
                ),
                3
            ),

            "baseline_power_db": round(
                float(
                    result[
                        "baseline_power_db"
                    ]
                ),
                3
            ),

            "excess_db": round(
                float(
                    result[
                        "excess_db"
                    ]
                ),
                3
            ),

            "velocity_est_kmh": round(
                float(
                    velocity_equivalent_kmh
                ),
                2
            ),

            "active_bins": int(
                result[
                    "active_bins"
                ]
            ),

            "event_hits": int(
                result[
                    "event_hits"
                ]
            ),

            "detected": True,
        }

        events = pd.DataFrame(
            [event]
        )

    else:

        events = pd.DataFrame(
            columns=[
                "timestamp",
                "doppler_hz",
                "snr_db",
                "peak_power_db",
                "baseline_power_db",
                "excess_db",
                "velocity_est_kmh",
                "active_bins",
                "event_hits",
                "detected",
            ]
        )

    events.to_csv(
        EVENTS_OUTPUT_PATH,
        index=False,
        encoding="utf-8"
    )

    return events


# ============================================================
# GENERAR metrics.json
# ============================================================

def write_metrics(
    result,
    velocity_equivalent_kmh,
    detection_config,
):

    detected = bool(
        result["detected"]
    )

    if detected:

        timestamp = str(
            result[
                "event_timestamp"
            ]
        )

        current_doppler_hz = float(
            result[
                "doppler_hz"
            ]
        )

        current_excess_db = float(
            result[
                "excess_db"
            ]
        )

        active_bins = int(
            result[
                "active_bins"
            ]
        )

        total_events = int(
            result[
                "event_hits"
            ]
        )

    else:

        timestamp = None
        current_doppler_hz = 0.0
        current_excess_db = 0.0
        active_bins = 0
        total_events = 0

    metrics = {

        "case_name": (
            detection_config[
                "case_name"
            ]
        ),

        "timestamp": timestamp,

        "current_doppler_hz": round(
            current_doppler_hz,
            3
        ),

        # Compatibilidad con dashboard existente.
        # Para Caso 2 equivale al exceso sobre reposo.
        "current_snr_db": round(
            current_excess_db,
            3
        ),

        "snr_definition": (
            "EXCESO_SOBRE_BASELINE_REPOSO_DB"
        ),

        "current_excess_db": round(
            current_excess_db,
            3
        ),

        "current_velocity_est_kmh": round(
            float(
                velocity_equivalent_kmh
            ),
            2
        ),

        "velocity_definition": (
            "VELOCIDAD_EQUIVALENTE_MODELO_DOPPLER_SIMPLIFICADO"
        ),

        "movement_detected": detected,

        "active_bins": active_bins,

        "minimum_active_bins": int(
            detection_config[
                "minimum_active_bins"
            ]
        ),

        "event_hits": int(
            result[
                "event_hits"
            ]
        ),

        "minimum_hits": int(
            detection_config[
                "minimum_hits"
            ]
        ),

        "baseline_instants": int(
            result[
                "baseline_instants"
            ]
        ),

        "total_instants": int(
            result[
                "total_instants"
            ]
        ),

        "total_events": total_events,

        # ----------------------------------------------------
        # AUN NO SE CALCULAN TASAS EXPERIMENTALES
        #
        # Existe observacion independiente del protocolo,
        # pero no sincronizacion temporal exacta.
        # ----------------------------------------------------

        "true_positives": 0,

        "false_positives": 0,

        "false_negatives": 0,

        "detection_rate_percent": 0.0,

        "false_positive_rate_percent": 0.0,

        "average_snr_db": round(
            current_excess_db,
            3
        ),

        "max_doppler_hz": round(
            abs(
                current_doppler_hz
            ),
            3
        ),

        "carrier_attenuation_db": 0.0,

        "ground_truth": (
            detection_config[
                "ground_truth"
            ]
        ),

        "ground_truth_timing": (
            detection_config[
                "ground_truth_timing"
            ]
        ),

        "validation_status": (
            "CORRELACION_TEMPORAL_APROXIMADA"
        ),

        "status": (
            detection_config[
                "status"
            ]
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

    ensure_processed_directory()

    (
        sdr_config,
        detection_config,
        spectrum,
        waterfall,
    ) = load_case_data()

    result = detect_human_movement(
        waterfall=waterfall,
        detection_config=(
            detection_config
        ),
    )

    if result["detected"]:

        velocity_equivalent_kmh = (
            calculate_equivalent_velocity(
                doppler_hz=(
                    result[
                        "doppler_hz"
                    ]
                ),

                center_frequency_hz=(
                    float(
                        sdr_config[
                            "center_frequency_hz"
                        ]
                    )
                ),

                geometry_factor=(
                    float(
                        detection_config[
                            "geometry_factor"
                        ]
                    )
                ),
            )
        )

    else:

        velocity_equivalent_kmh = 0.0

    detection_output = (
        write_detection_latest(
            result=result,

            velocity_equivalent_kmh=(
                velocity_equivalent_kmh
            ),

            detection_config=(
                detection_config
            ),
        )
    )

    events_output = (
        write_events(
            result=result,

            velocity_equivalent_kmh=(
                velocity_equivalent_kmh
            ),
        )
    )

    metrics_output = (
        write_metrics(
            result=result,

            velocity_equivalent_kmh=(
                velocity_equivalent_kmh
            ),

            detection_config=(
                detection_config
            ),
        )
    )

    print()
    print(
        "CASO 2 PROCESADO CORRECTAMENTE"
    )
    print(
        "================================"
    )

    print()

    print(
        f"Movimiento detectado: "
        f"{result['detected']}"
    )

    print(
        f"Evento representativo: "
        f"{result['event_timestamp']}"
    )

    print(
        f"Doppler representativo: "
        f"{result['doppler_hz']:.3f} Hz"
    )

    print(
        f"Exceso sobre reposo: "
        f"{result['excess_db']:.3f} dB"
    )

    print(
        f"Bins activos: "
        f"{result['active_bins']}"
    )

    print(
        f"Eventos validos detectados: "
        f"{result['event_hits']}"
    )

    print(
        f"Velocidad equivalente: "
        f"{velocity_equivalent_kmh:.2f} km/h"
    )

    print()

    print(
        "ARCHIVOS GENERADOS PARA STREAMLIT"
    )
    print(
        "---------------------------------"
    )

    print(
        DETECTION_OUTPUT_PATH
    )

    print(
        EVENTS_OUTPUT_PATH
    )

    print(
        METRICS_OUTPUT_PATH
    )

    print()

    print(
        "IMPORTANTE:"
    )

    print(
        "snr_db corresponde al exceso de potencia "
        "sobre el baseline de reposo."
    )

    print(
        "velocity_est_kmh es una velocidad equivalente "
        "del modelo Doppler simplificado."
    )

    print(
        "No representa una medicion exacta de la "
        "velocidad real de caminata."
    )