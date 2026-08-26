from pathlib import Path
import json

import pandas as pd


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CASE_DIR = BASE_DIR / "capturas" / "vehiculo" / "prueba_02"

WATERFALL_FILE = CASE_DIR / "waterfall.csv"
SPECTRUM_FILE = CASE_DIR / "spectrum_latest.csv"
SDR_CONFIG_FILE = CASE_DIR / "sdr_config.json"


# ============================================================
# CONFIGURACIÓN DEL DETECTOR VEHICULAR
# ============================================================

# Se excluye la zona muy próxima a DC / referencia directa.
MIN_DOPPLER_HZ = 1.0

# Banda compatible con el escenario vehicular ensayado.
# GNU Radio documentó un Doppler máximo teórico cercano a 5.52 Hz
# para 30 km/h en condiciones geométricas ideales.
MAX_DOPPLER_HZ = 6.5

# Primeros instantes utilizados para caracterizar el fondo.
BASELINE_INSTANTS = 10

# Aumento mínimo respecto del baseline para considerar
# una componente Doppler activa.
THRESHOLD_DB = 8.0

# Número mínimo de frecuencias Doppler ABSOLUTAS activas
# en un mismo instante.
#
# Importante:
# +f y -f se consideran una misma componente, para evitar
# contar dos veces la simetría espectral.
MINIMUM_ACTIVE_BINS = 4

# Número mínimo de instantes consecutivos que deben cumplir
# el criterio multibin.
MINIMUM_CONSECUTIVE_HITS = 3


# ============================================================
# CARGA DE DATOS
# ============================================================

def load_sdr_config() -> dict:
    if not SDR_CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró:\n{SDR_CONFIG_FILE}"
        )

    with open(SDR_CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_waterfall() -> pd.DataFrame:
    if not WATERFALL_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró:\n{WATERFALL_FILE}"
        )

    df = pd.read_csv(WATERFALL_FILE)

    required_columns = {
        "timestamp",
        "frequency_offset_hz",
        "power_db",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias: {missing}"
        )

    df["frequency_offset_hz"] = pd.to_numeric(
        df["frequency_offset_hz"],
        errors="coerce",
    )

    df["power_db"] = pd.to_numeric(
        df["power_db"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "timestamp",
            "frequency_offset_hz",
            "power_db",
        ]
    ).copy()

    return df


# ============================================================
# PREPARACIÓN DE LA BANDA DOPPLER
# ============================================================

def prepare_vehicle_band(
    waterfall: pd.DataFrame,
) -> pd.DataFrame:

    abs_frequency = waterfall["frequency_offset_hz"].abs()

    band = waterfall[
        (abs_frequency >= MIN_DOPPLER_HZ)
        & (abs_frequency <= MAX_DOPPLER_HZ)
    ].copy()

    # Convertimos ±f a una única frecuencia absoluta.
    band["abs_doppler_hz"] = (
        band["frequency_offset_hz"]
        .abs()
        .round(6)
    )

    # Colapsamos la simetría ±f.
    #
    # Si tenemos:
    # -1.367188 Hz
    # +1.367188 Hz
    #
    # pasan a representar UNA sola componente:
    # 1.367188 Hz
    collapsed = (
        band
        .groupby(
            ["timestamp", "abs_doppler_hz"],
            as_index=False,
        )
        .agg(
            power_db=("power_db", "mean")
        )
    )

    return collapsed


# ============================================================
# BASELINE
# ============================================================

def calculate_baseline(
    band: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], list[str]]:

    timestamps = sorted(
        band["timestamp"].unique()
    )

    if len(timestamps) <= BASELINE_INSTANTS:
        raise ValueError(
            "No existen suficientes instantes para "
            "crear baseline y evaluar movimiento."
        )

    baseline_timestamps = timestamps[:BASELINE_INSTANTS]

    baseline_data = band[
        band["timestamp"].isin(baseline_timestamps)
    ].copy()

    baseline = (
        baseline_data
        .groupby(
            "abs_doppler_hz",
            as_index=False,
        )["power_db"]
        .median()
        .rename(
            columns={
                "power_db": "baseline_db"
            }
        )
    )

    return baseline, baseline_timestamps, timestamps


# ============================================================
# ACTIVIDAD RESPECTO DEL REPOSO
# ============================================================

def calculate_activity(
    band: pd.DataFrame,
    baseline: pd.DataFrame,
) -> pd.DataFrame:

    activity = band.merge(
        baseline,
        on="abs_doppler_hz",
        how="left",
    )

    activity["excess_db"] = (
        activity["power_db"]
        - activity["baseline_db"]
    )

    activity["active"] = (
        activity["excess_db"] >= THRESHOLD_DB
    )

    return activity


# ============================================================
# RESUMEN POR INSTANTE
# ============================================================

def summarize_frames(
    activity: pd.DataFrame,
    baseline_timestamps: list[str],
) -> pd.DataFrame:

    rows = []

    timestamps = sorted(
        activity["timestamp"].unique()
    )

    for timestamp in timestamps:
        frame = activity[
            activity["timestamp"] == timestamp
        ].copy()

        if frame.empty:
            continue

        active_frame = frame[
            frame["active"]
        ].copy()

        active_bins = len(active_frame)

        max_excess = float(
            frame["excess_db"].max()
        )

        representative_row = frame.loc[
            frame["excess_db"].idxmax()
        ]

        representative_doppler = float(
            representative_row["abs_doppler_hz"]
        )

        representative_power = float(
            representative_row["power_db"]
        )

        representative_baseline = float(
            representative_row["baseline_db"]
        )

        valid_frame = (
            active_bins >= MINIMUM_ACTIVE_BINS
        )

        rows.append(
            {
                "timestamp": timestamp,
                "baseline": (
                    timestamp in baseline_timestamps
                ),
                "active_bins": int(active_bins),
                "max_excess_db": max_excess,
                "representative_doppler_hz": (
                    representative_doppler
                ),
                "representative_power_db": (
                    representative_power
                ),
                "representative_baseline_db": (
                    representative_baseline
                ),
                "valid_frame": bool(valid_frame),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# PERSISTENCIA TEMPORAL
# ============================================================

def find_consecutive_events(
    summary: pd.DataFrame,
) -> list[dict]:

    evaluation = summary[
        ~summary["baseline"]
    ].copy()

    evaluation = evaluation.reset_index(drop=True)

    events = []
    current_indices = []

    for index, row in evaluation.iterrows():

        if bool(row["valid_frame"]):
            current_indices.append(index)

        else:
            if current_indices:
                events.append(
                    build_event(
                        evaluation,
                        current_indices,
                    )
                )
                current_indices = []

    if current_indices:
        events.append(
            build_event(
                evaluation,
                current_indices,
            )
        )

    return events


def build_event(
    evaluation: pd.DataFrame,
    indices: list[int],
) -> dict:

    frames = evaluation.loc[indices].copy()

    representative_index = (
        frames
        .sort_values(
            by=[
                "active_bins",
                "max_excess_db",
            ],
            ascending=False,
        )
        .index[0]
    )

    representative = evaluation.loc[
        representative_index
    ]

    return {
        "start_timestamp": (
            frames.iloc[0]["timestamp"]
        ),
        "end_timestamp": (
            frames.iloc[-1]["timestamp"]
        ),
        "hits": int(len(frames)),
        "representative_timestamp": (
            representative["timestamp"]
        ),
        "representative_doppler_hz": float(
            representative[
                "representative_doppler_hz"
            ]
        ),
        "representative_excess_db": float(
            representative["max_excess_db"]
        ),
        "representative_active_bins": int(
            representative["active_bins"]
        ),
        "representative_power_db": float(
            representative[
                "representative_power_db"
            ]
        ),
        "representative_baseline_db": float(
            representative[
                "representative_baseline_db"
            ]
        ),
    }


# ============================================================
# DETECCIÓN FINAL
# ============================================================

def detect_vehicle(
    waterfall: pd.DataFrame,
) -> dict:

    band = prepare_vehicle_band(
        waterfall
    )

    (
        baseline,
        baseline_timestamps,
        timestamps,
    ) = calculate_baseline(
        band
    )

    activity = calculate_activity(
        band,
        baseline,
    )

    summary = summarize_frames(
        activity,
        baseline_timestamps,
    )

    events = find_consecutive_events(
        summary
    )

    valid_events = [
        event
        for event in events
        if event["hits"]
        >= MINIMUM_CONSECUTIVE_HITS
    ]

    detected = len(valid_events) > 0

    if detected:
        best_event = sorted(
            valid_events,
            key=lambda event: (
                event["hits"],
                event["representative_active_bins"],
                event["representative_excess_db"],
            ),
            reverse=True,
        )[0]

    else:
        best_event = None

    return {
        "detected": detected,
        "best_event": best_event,
        "events": events,
        "summary": summary,
        "activity": activity,
        "baseline_timestamps": baseline_timestamps,
        "total_instants": len(timestamps),
    }


# ============================================================
# PRESENTACIÓN EN CONSOLA
# ============================================================

def print_result(
    result: dict,
    sdr_config: dict,
) -> None:

    print()
    print("=" * 82)
    print("CASO VEHÍCULO — DETECTOR DOPPLER")
    print("=" * 82)

    print()
    print("ESCENARIO")

    print(
        "Frecuencia de referencia: "
        f"{sdr_config.get('center_frequency_hz', 0) / 1e6:.3f} MHz"
    )

    print(
        "Resolución espectral: "
        f"{sdr_config.get('frequency_resolution_hz', 0):.6f} Hz/bin"
    )

    print(
        "Velocidad conocida de la prueba: "
        f"{sdr_config.get('expected_speed_kmh', 'N/D')} km/h"
    )

    print(
        "Doppler máximo teórico documentado: "
        f"{sdr_config.get('expected_max_doppler_hz', 0):.3f} Hz"
    )

    print()
    print("CRITERIOS PYTHON")

    print(
        f"Banda Doppler: "
        f"{MIN_DOPPLER_HZ} a {MAX_DOPPLER_HZ} Hz"
    )

    print(
        f"Baseline: primeros "
        f"{BASELINE_INSTANTS} instantes"
    )

    print(
        f"Umbral: {THRESHOLD_DB} dB "
        "sobre baseline"
    )

    print(
        "Bins absolutos mínimos por instante: "
        f"{MINIMUM_ACTIVE_BINS}"
    )

    print(
        "Persistencia mínima: "
        f"{MINIMUM_CONSECUTIVE_HITS} "
        "instantes consecutivos"
    )

    print()
    print("RESULTADO")

    if not result["detected"]:
        print("Movimiento detectado: NO")

        print()
        print(
            "No se encontró un evento que cumpliera "
            "simultáneamente los criterios espectrales "
            "y temporales."
        )

        return

    event = result["best_event"]

    print("Movimiento detectado: SÍ")

    print(
        f"Inicio del evento: "
        f"{event['start_timestamp']}"
    )

    print(
        f"Fin del evento: "
        f"{event['end_timestamp']}"
    )

    print(
        f"Persistencia: "
        f"{event['hits']} instantes consecutivos"
    )

    print(
        f"Instante representativo: "
        f"{event['representative_timestamp']}"
    )

    print(
        f"Doppler representativo: "
        f"{event['representative_doppler_hz']:.3f} Hz"
    )

    print(
        f"Exceso máximo sobre baseline: "
        f"{event['representative_excess_db']:.3f} dB"
    )

    print(
        f"Bins absolutos activos: "
        f"{event['representative_active_bins']}"
    )

    print()
    print("INTERPRETACIÓN")

    print(
        "El sistema identificó un bloque temporal "
        "persistente de actividad Doppler de baja "
        "frecuencia compatible con el paso de un vehículo."
    )

    print(
        "La velocidad conocida del ensayo fue aproximadamente "
        f"{sdr_config.get('expected_speed_kmh', 'N/D')} km/h."
    )

    print(
        "No se calcula una velocidad real del vehículo a partir "
        "de un único bin Doppler porque el montaje es pasivo/"
        "biestático y el factor geométrico no fue calibrado."
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    sdr_config = load_sdr_config()

    waterfall = load_waterfall()

    result = detect_vehicle(
        waterfall
    )

    print_result(
        result,
        sdr_config,
    )


if __name__ == "__main__":
    main()