from pathlib import Path
import json

import pandas as pd


# ============================================================
# CONFIGURACION GENERAL
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "archive"
    / "caso_02_con_persona"
)

SDR_CONFIG_PATH = (
    CASE_DIR
    / "config"
    / "sdr_config.json"
)

DETECTION_CONFIG_PATH = (
    CASE_DIR
    / "config"
    / "detection_config.json"
)

SPECTRUM_PATH = (
    CASE_DIR
    / "data"
    / "realtime"
    / "spectrum_latest.csv"
)

WATERFALL_PATH = (
    CASE_DIR
    / "data"
    / "realtime"
    / "waterfall.csv"
)


# ============================================================
# FUNCIONES DE LECTURA
# ============================================================

def load_json(path):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def load_case_data():

    sdr_config = load_json(
        SDR_CONFIG_PATH
    )

    detection_config = load_json(
        DETECTION_CONFIG_PATH
    )

    spectrum = pd.read_csv(
        SPECTRUM_PATH
    )

    waterfall = pd.read_csv(
        WATERFALL_PATH
    )

    return (
        sdr_config,
        detection_config,
        spectrum,
        waterfall,
    )


# ============================================================
# PREPARAR BANDA DOPPLER HUMANA
# ============================================================

def prepare_human_band(
    waterfall,
    min_doppler_hz,
    max_doppler_hz,
):

    data = waterfall.copy()

    absolute_frequency = (
        data["frequency_offset_hz"]
        .abs()
    )

    data = data[
        (
            absolute_frequency
            >= min_doppler_hz
        )
        &
        (
            absolute_frequency
            <= max_doppler_hz
        )
    ].copy()

    return data


# ============================================================
# CALCULAR BASELINE DE REPOSO
# ============================================================

def calculate_rest_baseline(
    human_band,
    baseline_instants,
):

    timestamps = sorted(
        human_band[
            "timestamp"
        ].unique()
    )

    if (
        len(timestamps)
        <= baseline_instants
    ):

        raise ValueError(
            "No existen suficientes instantes "
            "para construir el baseline."
        )

    rest_timestamps = (
        timestamps[
            :baseline_instants
        ]
    )

    rest_data = human_band[
        human_band[
            "timestamp"
        ].isin(
            rest_timestamps
        )
    ]

    baseline = (
        rest_data
        .groupby(
            "frequency_offset_hz"
        )["power_db"]
        .median()
    )

    return (
        baseline,
        rest_timestamps,
    )


# ============================================================
# CALCULAR ACTIVIDAD SOBRE BASELINE
# ============================================================

def calculate_activity(
    human_band,
    baseline,
    threshold_db,
):

    data = human_band.copy()

    data["baseline_db"] = (
        data[
            "frequency_offset_hz"
        ].map(
            baseline
        )
    )

    data["excess_db"] = (
        data["power_db"]
        - data["baseline_db"]
    )

    data["active_bin"] = (
        data["excess_db"]
        >= threshold_db
    )

    activity = (
        data
        .groupby(
            "timestamp"
        )
        .agg(
            mean_excess_db=(
                "excess_db",
                "mean"
            ),
            max_excess_db=(
                "excess_db",
                "max"
            ),
            active_bins=(
                "active_bin",
                "sum"
            ),
        )
        .reset_index()
    )

    activity[
        "active_bins"
    ] = (
        activity[
            "active_bins"
        ].astype(
            int
        )
    )

    return (
        data,
        activity,
    )


# ============================================================
# DETECTAR EVENTO HUMANO
# ============================================================

def detect_human_movement(
    waterfall,
    detection_config,
):

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

    baseline_instants = int(
        detection_config[
            "baseline_instants"
        ]
    )

    minimum_active_bins = int(
        detection_config[
            "minimum_active_bins"
        ]
    )

    minimum_hits = int(
        detection_config[
            "minimum_hits"
        ]
    )

    # --------------------------------------------------------
    # 1. EXTRAER BANDA DE MOVIMIENTO HUMANO
    # --------------------------------------------------------

    human_band = (
        prepare_human_band(
            waterfall=waterfall,
            min_doppler_hz=(
                min_doppler_hz
            ),
            max_doppler_hz=(
                max_doppler_hz
            ),
        )
    )

    # --------------------------------------------------------
    # 2. BASELINE DE REPOSO
    # --------------------------------------------------------

    (
        baseline,
        rest_timestamps,
    ) = calculate_rest_baseline(
        human_band=human_band,
        baseline_instants=(
            baseline_instants
        ),
    )

    # --------------------------------------------------------
    # 3. ACTIVIDAD DOPPLER
    # --------------------------------------------------------

    (
        activity_data,
        activity_summary,
    ) = calculate_activity(
        human_band=human_band,
        baseline=baseline,
        threshold_db=(
            threshold_db
        ),
    )

    # --------------------------------------------------------
    # 4. EXCLUIR LOS INSTANTES UTILIZADOS COMO REPOSO
    # --------------------------------------------------------

    evaluation = (
        activity_summary[
            ~activity_summary[
                "timestamp"
            ].isin(
                rest_timestamps
            )
        ].copy()
    )

    # --------------------------------------------------------
    # 5. BUSCAR INSTANTES QUE CUMPLAN EL CRITERIO MULTIBIN
    # --------------------------------------------------------

    valid_events = (
        evaluation[
            evaluation[
                "active_bins"
            ]
            >= minimum_active_bins
        ]
        .copy()
    )

    event_hits = int(
        len(
            valid_events
        )
    )

    detected = (
        event_hits
        >= minimum_hits
    )

    # --------------------------------------------------------
    # 6. CASO SIN DETECCION
    # --------------------------------------------------------

    if not detected:

        return {
            "detected": False,
            "event_timestamp": None,
            "doppler_hz": 0.0,
            "peak_power_db": 0.0,
            "baseline_power_db": 0.0,
            "excess_db": 0.0,
            "active_bins": 0,
            "event_hits": event_hits,
            "total_instants": int(
                waterfall[
                    "timestamp"
                ].nunique()
            ),
            "baseline_instants": (
                baseline_instants
            ),
            "rest_start": (
                rest_timestamps[0]
            ),
            "rest_end": (
                rest_timestamps[-1]
            ),
        }

    # --------------------------------------------------------
    # 7. SELECCIONAR EL EVENTO MAS REPRESENTATIVO
    # --------------------------------------------------------

    best_event = (
        valid_events
        .sort_values(
            by=[
                "active_bins",
                "max_excess_db",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .iloc[0]
    )

    best_timestamp = (
        best_event[
            "timestamp"
        ]
    )

    # --------------------------------------------------------
    # 8. IDENTIFICAR EL BIN DOPPLER MAS FUERTE
    # --------------------------------------------------------

    event_bins = (
        activity_data[
            activity_data[
                "timestamp"
            ]
            == best_timestamp
        ]
        .sort_values(
            "excess_db",
            ascending=False
        )
    )

    representative_bin = (
        event_bins.iloc[0]
    )

    # --------------------------------------------------------
    # 9. RESULTADO
    # --------------------------------------------------------

    return {
        "detected": True,

        "event_timestamp": (
            best_timestamp
        ),

        "doppler_hz": float(
            representative_bin[
                "frequency_offset_hz"
            ]
        ),

        "peak_power_db": float(
            representative_bin[
                "power_db"
            ]
        ),

        "baseline_power_db": float(
            representative_bin[
                "baseline_db"
            ]
        ),

        "excess_db": float(
            representative_bin[
                "excess_db"
            ]
        ),

        "active_bins": int(
            best_event[
                "active_bins"
            ]
        ),

        "event_hits": int(
            event_hits
        ),

        "total_instants": int(
            waterfall[
                "timestamp"
            ].nunique()
        ),

        "baseline_instants": (
            baseline_instants
        ),

        "rest_start": (
            rest_timestamps[0]
        ),

        "rest_end": (
            rest_timestamps[-1]
        ),
    }


# ============================================================
# VELOCIDAD EQUIVALENTE
# ============================================================

def calculate_equivalent_velocity(
    doppler_hz,
    center_frequency_hz,
    geometry_factor,
):

    speed_of_light = (
        299_792_458.0
    )

    wavelength = (
        speed_of_light
        / center_frequency_hz
    )

    velocity_mps = (
        abs(
            doppler_hz
        )
        * wavelength
        / geometry_factor
    )

    velocity_kmh = (
        velocity_mps
        * 3.6
    )

    return velocity_kmh


# ============================================================
# EJECUCION DIRECTA
# ============================================================

if __name__ == "__main__":

    (
        sdr_config,
        detection_config,
        spectrum,
        waterfall,
    ) = load_case_data()

    result = (
        detect_human_movement(
            waterfall=waterfall,
            detection_config=(
                detection_config
            ),
        )
    )

    if result["detected"]:

        velocity_equivalent = (
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

        velocity_equivalent = 0.0

    print()
    print(
        "CASO 2 - DETECCION DE MOVIMIENTO HUMANO"
    )
    print(
        "========================================"
    )

    print(
        f"Caso: "
        f"{detection_config['case_name']}"
    )

    print(
        f"Modo: "
        f"{detection_config['detection_mode']}"
    )

    print()

    print(
        "BASELINE DE REPOSO"
    )
    print(
        "------------------"
    )

    print(
        f"Instantes utilizados: "
        f"{result['baseline_instants']}"
    )

    print(
        f"Inicio reposo: "
        f"{result['rest_start']}"
    )

    print(
        f"Fin reposo: "
        f"{result['rest_end']}"
    )

    print()

    print(
        "CRITERIOS"
    )
    print(
        "---------"
    )

    print(
        f"Banda Doppler: "
        f"{detection_config['min_doppler_hz']} "
        f"a "
        f"{detection_config['max_doppler_hz']} Hz"
    )

    print(
        f"Umbral: "
        f"{detection_config['threshold_db']} dB"
    )

    print(
        f"Bins activos requeridos: "
        f"{detection_config['minimum_active_bins']}"
    )

    print()

    print(
        "RESULTADO"
    )
    print(
        "---------"
    )

    print(
        f"Movimiento detectado: "
        f"{result['detected']}"
    )

    print(
        f"Instantes con evento valido: "
        f"{result['event_hits']}"
    )

    print(
        f"Total de instantes: "
        f"{result['total_instants']}"
    )

    if result["detected"]:

        print(
            f"Evento representativo: "
            f"{result['event_timestamp']}"
        )

        print(
            f"Doppler representativo: "
            f"{result['doppler_hz']:.3f} Hz"
        )

        print(
            f"Potencia del bin: "
            f"{result['peak_power_db']:.3f} dB"
        )

        print(
            f"Baseline del bin: "
            f"{result['baseline_power_db']:.3f} dB"
        )

        print(
            f"Exceso sobre reposo: "
            f"{result['excess_db']:.3f} dB"
        )

        print(
            f"Bins activos simultaneos: "
            f"{result['active_bins']}"
        )

        print(
            f"Velocidad equivalente: "
            f"{velocity_equivalent:.2f} km/h"
        )

        print()

        print(
            "NOTA:"
        )

        print(
            "La velocidad es una estimacion equivalente "
            "obtenida mediante un modelo Doppler simplificado."
        )

        print(
            "No debe interpretarse como una medicion exacta "
            "de la velocidad real de caminata."
        )