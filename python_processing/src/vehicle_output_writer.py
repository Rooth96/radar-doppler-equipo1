from pathlib import Path
import json
import csv

from vehicle_detection import (
    load_sdr_config,
    load_waterfall,
    detect_vehicle,
    MIN_DOPPLER_HZ,
    MAX_DOPPLER_HZ,
    BASELINE_INSTANTS,
    THRESHOLD_DB,
    MINIMUM_ACTIVE_BINS,
    MINIMUM_CONSECUTIVE_HITS,
)


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CASE_DIR = (
    BASE_DIR
    / "capturas"
    / "vehiculo"
    / "prueba_02"
)

PROCESSED_DIR = CASE_DIR / "processed"

DETECTION_FILE = (
    PROCESSED_DIR
    / "detection_latest.json"
)

EVENTS_FILE = (
    PROCESSED_DIR
    / "events.csv"
)

METRICS_FILE = (
    PROCESSED_DIR
    / "metrics.json"
)

DETECTION_CONFIG_FILE = (
    CASE_DIR
    / "detection_config.json"
)


# ============================================================
# UTILIDADES
# ============================================================

def round_value(value, digits=3):
    if value is None:
        return None

    return round(
        float(value),
        digits,
    )


# ============================================================
# CONFIGURACIÓN DEL DETECTOR
# ============================================================

def build_detection_config(
    sdr_config: dict,
) -> dict:

    return {
        "case_name": (
            "CASO 2 - VEHICULO OBJETIVO 30 KM/H"
        ),
        "detection_mode": (
            "VEHICLE_LOW_DOPPLER_PERSISTENT_MULTIBIN"
        ),

        "min_doppler_hz": (
            MIN_DOPPLER_HZ
        ),

        "max_doppler_hz": (
            MAX_DOPPLER_HZ
        ),

        "threshold_db": (
            THRESHOLD_DB
        ),

        "baseline_instants": (
            BASELINE_INSTANTS
        ),

        "minimum_active_bins": (
            MINIMUM_ACTIVE_BINS
        ),

        "minimum_consecutive_hits": (
            MINIMUM_CONSECUTIVE_HITS
        ),

        "expected_speed_kmh": (
            sdr_config.get(
                "expected_speed_kmh"
            )
        ),

        "expected_max_doppler_hz": (
            sdr_config.get(
                "expected_max_doppler_hz"
            )
        ),

        "geometry_factor": None,

        "geometry_status": (
            "NO_CALIBRADO"
        ),

        "velocity_estimation_status": (
            "NO_CALIBRADA_GEOMETRIA_BIESTATICA"
        ),

        "ground_truth": (
            "VEHICULO_REAL_APROX_30_KMH"
        ),

        "ground_truth_timing": (
            "PENDIENTE_CONFIRMACION_TEMPORAL"
        ),

        "status": (
            "DETECCION_VEHICULAR_DATOS_REALES"
        ),
    }


# ============================================================
# DETECTION_LATEST.JSON
# ============================================================

def build_detection_output(
    result: dict,
    sdr_config: dict,
) -> dict:

    detected = bool(
        result["detected"]
    )

    event = result["best_event"]

    if not detected or event is None:
        return {
            "case_name": (
                "CASO 2 - VEHICULO OBJETIVO 30 KM/H"
            ),

            "detection_mode": (
                "VEHICLE_LOW_DOPPLER_PERSISTENT_MULTIBIN"
            ),

            "timestamp": None,

            "detected": False,

            "doppler_hz": 0.0,

            "snr_db": 0.0,

            "snr_definition": (
                "EXCESO_SOBRE_BASELINE_DB"
            ),

            "excess_db": 0.0,

            "velocity_est_kmh": None,

            "known_speed_kmh": (
                sdr_config.get(
                    "expected_speed_kmh"
                )
            ),

            "velocity_definition": (
                "NO_CALIBRADA_GEOMETRIA_BIESTATICA"
            ),

            "active_bins": 0,

            "persistence_hits": 0,

            "movement_detected": False,

            "validation_status": (
                "SIN_EVENTO_DOPPLER_VALIDO"
            ),
        }

    return {
        "case_name": (
            "CASO 2 - VEHICULO OBJETIVO 30 KM/H"
        ),

        "detection_mode": (
            "VEHICLE_LOW_DOPPLER_PERSISTENT_MULTIBIN"
        ),

        "timestamp": (
            event[
                "representative_timestamp"
            ]
        ),

        "event_start": (
            event[
                "start_timestamp"
            ]
        ),

        "event_end": (
            event[
                "end_timestamp"
            ]
        ),

        "detected": True,

        "doppler_hz": round_value(
            event[
                "representative_doppler_hz"
            ]
        ),

        # Este campo se conserva por compatibilidad
        # con el contrato anterior de Streamlit.
        # NO representa SNR clásico.
        "snr_db": round_value(
            event[
                "representative_excess_db"
            ]
        ),

        "snr_definition": (
            "EXCESO_SOBRE_BASELINE_DB"
        ),

        "excess_db": round_value(
            event[
                "representative_excess_db"
            ]
        ),

        "peak_power_db": round_value(
            event[
                "representative_power_db"
            ]
        ),

        "baseline_power_db": round_value(
            event[
                "representative_baseline_db"
            ]
        ),

        # No se entrega velocidad calculada porque
        # la geometría biestática no está calibrada.
        "velocity_est_kmh": None,

        # Sí conservamos la velocidad conocida
        # experimentalmente durante la prueba.
        "known_speed_kmh": (
            sdr_config.get(
                "expected_speed_kmh"
            )
        ),

        "velocity_definition": (
            "NO_CALIBRADA_GEOMETRIA_BIESTATICA"
        ),

        "expected_max_doppler_hz": (
            round_value(
                sdr_config.get(
                    "expected_max_doppler_hz"
                )
            )
        ),

        "active_bins": int(
            event[
                "representative_active_bins"
            ]
        ),

        "minimum_active_bins": (
            MINIMUM_ACTIVE_BINS
        ),

        "persistence_hits": int(
            event[
                "hits"
            ]
        ),

        "minimum_hits": (
            MINIMUM_CONSECUTIVE_HITS
        ),

        "baseline_instants": (
            BASELINE_INSTANTS
        ),

        "total_instants": int(
            result[
                "total_instants"
            ]
        ),

        "doppler_band_min_hz": (
            MIN_DOPPLER_HZ
        ),

        "doppler_band_max_hz": (
            MAX_DOPPLER_HZ
        ),

        "threshold_db": (
            THRESHOLD_DB
        ),

        "ground_truth": (
            "VEHICULO_REAL_APROX_30_KMH"
        ),

        "ground_truth_timing": (
            "PENDIENTE_CONFIRMACION_TEMPORAL"
        ),

        "validation_status": (
            "EVENTO_DOPPLER_COMPATIBLE_CON_VEHICULO"
        ),

        "status": (
            "DETECCION_VEHICULAR_DATOS_REALES"
        ),
    }


# ============================================================
# EVENTS.CSV
# ============================================================

def write_events_csv(
    result: dict,
) -> None:

    headers = [
        "timestamp",
        "event_start",
        "event_end",
        "doppler_hz",
        "snr_db",
        "excess_db",
        "peak_power_db",
        "baseline_power_db",
        "velocity_est_kmh",
        "active_bins",
        "event_hits",
        "detected",
    ]

    with open(
        EVENTS_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=headers,
        )

        writer.writeheader()

        valid_events = [
            event
            for event in result["events"]
            if (
                event["hits"]
                >= MINIMUM_CONSECUTIVE_HITS
            )
        ]

        for event in valid_events:

            writer.writerow(
                {
                    "timestamp": (
                        event[
                            "representative_timestamp"
                        ]
                    ),

                    "event_start": (
                        event[
                            "start_timestamp"
                        ]
                    ),

                    "event_end": (
                        event[
                            "end_timestamp"
                        ]
                    ),

                    "doppler_hz": round_value(
                        event[
                            "representative_doppler_hz"
                        ]
                    ),

                    # Compatibilidad.
                    # Es exceso sobre baseline.
                    "snr_db": round_value(
                        event[
                            "representative_excess_db"
                        ]
                    ),

                    "excess_db": round_value(
                        event[
                            "representative_excess_db"
                        ]
                    ),

                    "peak_power_db": round_value(
                        event[
                            "representative_power_db"
                        ]
                    ),

                    "baseline_power_db": round_value(
                        event[
                            "representative_baseline_db"
                        ]
                    ),

                    "velocity_est_kmh": "",

                    "active_bins": int(
                        event[
                            "representative_active_bins"
                        ]
                    ),

                    "event_hits": int(
                        event["hits"]
                    ),

                    "detected": True,
                }
            )


# ============================================================
# METRICS.JSON
# ============================================================

def build_metrics(
    result: dict,
    sdr_config: dict,
) -> dict:

    detected = bool(
        result["detected"]
    )

    event = result["best_event"]

    if detected and event:

        current_doppler = round_value(
            event[
                "representative_doppler_hz"
            ]
        )

        current_excess = round_value(
            event[
                "representative_excess_db"
            ]
        )

        active_bins = int(
            event[
                "representative_active_bins"
            ]
        )

        event_hits = int(
            event["hits"]
        )

    else:

        current_doppler = 0.0
        current_excess = 0.0
        active_bins = 0
        event_hits = 0

    valid_events = [
        event_item
        for event_item in result["events"]
        if (
            event_item["hits"]
            >= MINIMUM_CONSECUTIVE_HITS
        )
    ]

    return {
        "case_name": (
            "CASO 2 - VEHICULO OBJETIVO 30 KM/H"
        ),

        "timestamp": (
            event[
                "representative_timestamp"
            ]
            if event
            else None
        ),

        "current_doppler_hz": (
            current_doppler
        ),

        # Compatibilidad con dashboard anterior.
        "current_snr_db": (
            current_excess
        ),

        "snr_definition": (
            "EXCESO_SOBRE_BASELINE_DB"
        ),

        "current_excess_db": (
            current_excess
        ),

        "current_velocity_est_kmh": None,

        "known_speed_kmh": (
            sdr_config.get(
                "expected_speed_kmh"
            )
        ),

        "velocity_definition": (
            "NO_CALIBRADA_GEOMETRIA_BIESTATICA"
        ),

        "movement_detected": (
            detected
        ),

        "active_bins": (
            active_bins
        ),

        "minimum_active_bins": (
            MINIMUM_ACTIVE_BINS
        ),

        "event_hits": (
            event_hits
        ),

        "minimum_hits": (
            MINIMUM_CONSECUTIVE_HITS
        ),

        "baseline_instants": (
            BASELINE_INSTANTS
        ),

        "total_instants": int(
            result[
                "total_instants"
            ]
        ),

        "total_events": len(
            valid_events
        ),

        # No calculamos TP/FP/FN porque no existe
        # una serie temporal etiquetada sincronizada.
        "true_positives": 0,

        "false_positives": 0,

        "false_negatives": 0,

        "detection_rate_percent": 0.0,

        "false_positive_rate_percent": 0.0,

        "max_doppler_hz": (
            current_doppler
        ),

        "expected_max_doppler_hz": (
            round_value(
                sdr_config.get(
                    "expected_max_doppler_hz"
                )
            )
        ),

        "threshold_db": (
            THRESHOLD_DB
        ),

        "ground_truth": (
            "VEHICULO_REAL_APROX_30_KMH"
        ),

        "ground_truth_timing": (
            "PENDIENTE_CONFIRMACION_TEMPORAL"
        ),

        "validation_status": (
            "EVENTO_DOPPLER_COMPATIBLE_CON_VEHICULO"
            if detected
            else "SIN_EVENTO_DOPPLER_VALIDO"
        ),

        "status": (
            "DETECCION_VEHICULAR_DATOS_REALES"
        ),
    }


# ============================================================
# ESCRITURA JSON
# ============================================================

def write_json(
    path: Path,
    data: dict,
) -> None:

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sdr_config = (
        load_sdr_config()
    )

    waterfall = (
        load_waterfall()
    )

    result = detect_vehicle(
        waterfall
    )

    detection_config = (
        build_detection_config(
            sdr_config
        )
    )

    detection_output = (
        build_detection_output(
            result,
            sdr_config,
        )
    )

    metrics = build_metrics(
        result,
        sdr_config,
    )

    write_json(
        DETECTION_CONFIG_FILE,
        detection_config,
    )

    write_json(
        DETECTION_FILE,
        detection_output,
    )

    write_events_csv(
        result
    )

    write_json(
        METRICS_FILE,
        metrics,
    )

    print()
    print("=" * 82)
    print(
        "CASO VEHÍCULO PROCESADO CORRECTAMENTE"
    )
    print("=" * 82)

    print()

    print(
        "Movimiento detectado: "
        f"{result['detected']}"
    )

    if result["detected"]:

        event = result[
            "best_event"
        ]

        print(
            "Inicio evento: "
            f"{event['start_timestamp']}"
        )

        print(
            "Fin evento: "
            f"{event['end_timestamp']}"
        )

        print(
            "Evento representativo: "
            f"{event['representative_timestamp']}"
        )

        print(
            "Doppler representativo: "
            f"{event['representative_doppler_hz']:.3f} Hz"
        )

        print(
            "Exceso sobre baseline: "
            f"{event['representative_excess_db']:.3f} dB"
        )

        print(
            "Bins absolutos activos: "
            f"{event['representative_active_bins']}"
        )

        print(
            "Persistencia: "
            f"{event['hits']} instantes"
        )

    print()

    print(
        "Velocidad conocida de la prueba: "
        f"{sdr_config.get('expected_speed_kmh')} km/h"
    )

    print(
        "Velocidad Doppler calculada: "
        "NO CALIBRADA"
    )

    print()

    print(
        "ARCHIVOS GENERADOS PARA STREAMLIT"
    )

    print(
        DETECTION_CONFIG_FILE
    )

    print(
        DETECTION_FILE
    )

    print(
        EVENTS_FILE
    )

    print(
        METRICS_FILE
    )


if __name__ == "__main__":
    main()