from pathlib import Path

import pandas as pd


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CASE_DIR = BASE_DIR / "capturas" / "vehiculo" / "prueba_02"

WATERFALL_FILE = CASE_DIR / "waterfall.csv"
SPECTRUM_FILE = CASE_DIR / "spectrum_latest.csv"
CONFIG_FILE = CASE_DIR / "sdr_config.json"


# ============================================================
# PARÁMETROS EXPLORATORIOS
# ============================================================

# La documentación GNU Radio propone inicialmente 1–10 Hz.
MIN_DOPPLER_HZ = 1.0
MAX_DOPPLER_HZ = 10.0

# Para un vehículo objetivo cercano a 30 km/h,
# el Doppler máximo teórico documentado es ~5.52 Hz.
# Usamos 6.5 Hz solamente como banda física de referencia
# con un pequeño margen, NO como criterio final.
PHYSICAL_REFERENCE_MAX_HZ = 6.5

# Según el procedimiento experimental se esperaba
# un período inicial sin vehículo.
BASELINE_INSTANTS = 10

# Umbrales que vamos a comparar exploratoriamente.
THRESHOLDS_DB = [3.0, 6.0, 8.0, 10.0]


# ============================================================
# FUNCIONES
# ============================================================

def load_waterfall() -> pd.DataFrame:
    if not WATERFALL_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo waterfall:\n{WATERFALL_FILE}"
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
            f"Faltan columnas obligatorias en waterfall.csv: {missing}"
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
        subset=["timestamp", "frequency_offset_hz", "power_db"]
    ).copy()

    # Redondeamos solo para asegurar correspondencia exacta entre bins.
    df["frequency_bin"] = df["frequency_offset_hz"].round(6)

    return df


def prepare_doppler_band(df: pd.DataFrame) -> pd.DataFrame:
    abs_frequency = df["frequency_offset_hz"].abs()

    band = df[
        (abs_frequency >= MIN_DOPPLER_HZ)
        & (abs_frequency <= MAX_DOPPLER_HZ)
    ].copy()

    return band


def calculate_baseline(
    band: pd.DataFrame,
    timestamps: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    if len(timestamps) <= BASELINE_INSTANTS:
        raise ValueError(
            "La captura no contiene suficientes instantes "
            "para formar baseline y evaluar movimiento."
        )

    baseline_timestamps = timestamps[:BASELINE_INSTANTS]

    baseline_data = band[
        band["timestamp"].isin(baseline_timestamps)
    ].copy()

    baseline = (
        baseline_data
        .groupby("frequency_bin", as_index=False)["power_db"]
        .median()
        .rename(columns={"power_db": "baseline_db"})
    )

    return baseline, baseline_timestamps


def calculate_activity(
    band: pd.DataFrame,
    baseline: pd.DataFrame,
) -> pd.DataFrame:
    activity = band.merge(
        baseline,
        on="frequency_bin",
        how="left",
    )

    activity["excess_db"] = (
        activity["power_db"] - activity["baseline_db"]
    )

    return activity


def summarize_timestamps(
    activity: pd.DataFrame,
    baseline_timestamps: list[str],
) -> pd.DataFrame:
    rows = []

    timestamps = sorted(activity["timestamp"].unique())

    for timestamp in timestamps:
        frame = activity[
            activity["timestamp"] == timestamp
        ].copy()

        if frame.empty:
            continue

        row = {
            "timestamp": timestamp,
            "baseline": timestamp in baseline_timestamps,
            "mean_excess_db": frame["excess_db"].mean(),
            "median_excess_db": frame["excess_db"].median(),
            "max_excess_db": frame["excess_db"].max(),
        }

        for threshold in THRESHOLDS_DB:
            column_name = f"bins_gt_{int(threshold)}db"

            row[column_name] = int(
                (frame["excess_db"] >= threshold).sum()
            )

        physical_frame = frame[
            frame["frequency_offset_hz"].abs()
            <= PHYSICAL_REFERENCE_MAX_HZ
        ]

        row["physical_bins_gt_6db"] = int(
            (physical_frame["excess_db"] >= 6.0).sum()
        )

        row["physical_bins_gt_8db"] = int(
            (physical_frame["excess_db"] >= 8.0).sum()
        )

        representative = frame.loc[
            frame["excess_db"].idxmax()
        ]

        row["representative_doppler_hz"] = float(
            representative["frequency_offset_hz"]
        )

        row["representative_power_db"] = float(
            representative["power_db"]
        )

        row["representative_baseline_db"] = float(
            representative["baseline_db"]
        )

        rows.append(row)

    return pd.DataFrame(rows)


def print_top_frames(
    summary: pd.DataFrame,
    baseline_timestamps: list[str],
) -> None:
    evaluation = summary[
        ~summary["timestamp"].isin(baseline_timestamps)
    ].copy()

    ranked = evaluation.sort_values(
        by=[
            "physical_bins_gt_8db",
            "bins_gt_8db",
            "physical_bins_gt_6db",
            "max_excess_db",
        ],
        ascending=False,
    )

    print()
    print("=" * 90)
    print("INSTANCIAS MÁS ACTIVAS DESPUÉS DEL BASELINE")
    print("=" * 90)

    columns = [
        "timestamp",
        "max_excess_db",
        "bins_gt_6db",
        "bins_gt_8db",
        "physical_bins_gt_6db",
        "physical_bins_gt_8db",
        "representative_doppler_hz",
    ]

    print(
        ranked[columns]
        .head(15)
        .to_string(index=False)
    )


def print_strongest_frame(
    activity: pd.DataFrame,
    summary: pd.DataFrame,
    baseline_timestamps: list[str],
) -> None:
    evaluation = summary[
        ~summary["timestamp"].isin(baseline_timestamps)
    ].copy()

    if evaluation.empty:
        return

    ranked = evaluation.sort_values(
        by=[
            "physical_bins_gt_8db",
            "bins_gt_8db",
            "physical_bins_gt_6db",
            "max_excess_db",
        ],
        ascending=False,
    )

    strongest_timestamp = ranked.iloc[0]["timestamp"]

    strongest = activity[
        activity["timestamp"] == strongest_timestamp
    ].copy()

    strongest = strongest.sort_values(
        "excess_db",
        ascending=False,
    )

    print()
    print("=" * 90)
    print("BINS MÁS FUERTES DEL INSTANTE PRINCIPAL")
    print("=" * 90)

    print(f"Timestamp: {strongest_timestamp}")
    print()

    columns = [
        "frequency_offset_hz",
        "power_db",
        "baseline_db",
        "excess_db",
    ]

    print(
        strongest[columns]
        .head(20)
        .to_string(index=False)
    )


def main() -> None:
    print("=" * 90)
    print("ANÁLISIS EXPLORATORIO — CASO VEHÍCULO")
    print("=" * 90)

    waterfall = load_waterfall()

    timestamps = sorted(
        waterfall["timestamp"].unique()
    )

    bins_per_timestamp = (
        waterfall
        .groupby("timestamp")
        .size()
    )

    print()
    print("ARCHIVO")
    print(f"Waterfall: {WATERFALL_FILE}")

    print()
    print("ESTRUCTURA DE LA CAPTURA")
    print(f"Registros totales: {len(waterfall)}")
    print(f"Instantes únicos: {len(timestamps)}")
    print(f"Primer instante: {timestamps[0]}")
    print(f"Último instante: {timestamps[-1]}")
    print(
        "Bins por instante: "
        f"mín={bins_per_timestamp.min()}, "
        f"máx={bins_per_timestamp.max()}"
    )

    print()
    print("RANGO COMPLETO")
    print(
        f"Frecuencia mínima: "
        f"{waterfall['frequency_offset_hz'].min():.6f} Hz"
    )
    print(
        f"Frecuencia máxima: "
        f"{waterfall['frequency_offset_hz'].max():.6f} Hz"
    )

    unique_frequencies = sorted(
        waterfall["frequency_offset_hz"].unique()
    )

    if len(unique_frequencies) > 1:
        resolution = (
            pd.Series(unique_frequencies)
            .diff()
            .dropna()
            .abs()
            .median()
        )

        print(
            f"Resolución observada aproximada: "
            f"{resolution:.6f} Hz/bin"
        )

    band = prepare_doppler_band(waterfall)

    baseline, baseline_timestamps = calculate_baseline(
        band,
        timestamps,
    )

    activity = calculate_activity(
        band,
        baseline,
    )

    summary = summarize_timestamps(
        activity,
        baseline_timestamps,
    )

    print()
    print("CONFIGURACIÓN EXPLORATORIA")
    print(
        f"Banda analizada: "
        f"|f| = {MIN_DOPPLER_HZ} a {MAX_DOPPLER_HZ} Hz"
    )
    print(
        f"Banda física de referencia: "
        f"|f| <= {PHYSICAL_REFERENCE_MAX_HZ} Hz"
    )
    print(
        f"Instantes usados como baseline: "
        f"{BASELINE_INSTANTS}"
    )

    print()
    print("BASELINE")
    print(f"Inicio: {baseline_timestamps[0]}")
    print(f"Fin: {baseline_timestamps[-1]}")

    print_top_frames(
        summary,
        baseline_timestamps,
    )

    print_strongest_frame(
        activity,
        summary,
        baseline_timestamps,
    )

    print()
    print("=" * 90)
    print("IMPORTANTE")
    print("=" * 90)
    print(
        "Este programa NO decide todavía si existe vehículo."
    )
    print(
        "Solo compara cada instante con el período inicial "
        "de referencia y muestra dónde aparece actividad Doppler."
    )
    print(
        "Después de revisar estos resultados se definirán "
        "umbral, persistencia y criterio multibin."
    )


if __name__ == "__main__":
    main()