import json
from pathlib import Path

import pandas as pd


# ============================================================
# RUTA RAIZ DEL PROYECTO
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# ARCHIVOS DE CONFIGURACION
# ============================================================

SDR_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "sdr_config.json"
)

DETECTION_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "detection_config.json"
)


# ============================================================
# ARCHIVOS PROVENIENTES DE GNU RADIO
# ============================================================

SPECTRUM_PATH = (
    PROJECT_ROOT
    / "data"
    / "realtime"
    / "spectrum_latest.csv"
)

WATERFALL_PATH = (
    PROJECT_ROOT
    / "data"
    / "realtime"
    / "waterfall.csv"
)


# ============================================================
# LEER CONFIGURACION SDR
# ============================================================

def load_sdr_config():
    """
    Lee y valida la configuracion del SDR
    generada por GNU Radio.
    """

    with open(
        SDR_CONFIG_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

    required_fields = [
        "timestamp",
        "center_frequency_hz",
        "sample_rate_hz",
        "gain_db",
        "fft_size",
        "frequency_resolution_hz",
        "window_type",
        "source_device",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in config
    ]

    if missing_fields:

        raise ValueError(
            "Faltan campos obligatorios "
            "en sdr_config.json: "
            f"{missing_fields}"
        )

    return config


# ============================================================
# LEER CONFIGURACION DEL DETECTOR
# ============================================================

def load_detection_config():
    """
    Lee y valida los parametros configurables
    utilizados por el procesamiento Python.

    Los parametros Doppler permanecen sujetos
    a calibracion experimental con datos reales.
    """

    with open(
        DETECTION_CONFIG_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

    required_fields = [
        "exclusion_hz",
        "reference_notch_hz",
        "min_doppler_hz",
        "max_doppler_hz",
        "threshold_db",
        "minimum_hits",
        "geometry_factor",
        "poll_interval_seconds",
        "status",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in config
    ]

    if missing_fields:

        raise ValueError(
            "Faltan campos obligatorios "
            "en detection_config.json: "
            f"{missing_fields}"
        )

    # --------------------------------------------------------
    # VALIDACIONES BASICAS
    # --------------------------------------------------------

    if config["exclusion_hz"] < 0:

        raise ValueError(
            "exclusion_hz no puede ser negativo."
        )

    if config["reference_notch_hz"] <= 0:

        raise ValueError(
            "reference_notch_hz "
            "debe ser mayor que 0."
        )

    if config["min_doppler_hz"] <= 0:

        raise ValueError(
            "min_doppler_hz "
            "debe ser mayor que 0."
        )

    if config["max_doppler_hz"] <= 0:

        raise ValueError(
            "max_doppler_hz "
            "debe ser mayor que 0."
        )

    if (
        config["max_doppler_hz"]
        <= config["min_doppler_hz"]
    ):

        raise ValueError(
            "max_doppler_hz debe ser mayor "
            "que min_doppler_hz."
        )

    if config["threshold_db"] < 0:

        raise ValueError(
            "threshold_db no puede ser negativo."
        )

    if config["minimum_hits"] < 1:

        raise ValueError(
            "minimum_hits debe ser al menos 1."
        )

    if not (
        0
        < config["geometry_factor"]
        <= 2
    ):

        raise ValueError(
            "geometry_factor debe ser "
            "mayor que 0 y menor o igual a 2."
        )

    if config["poll_interval_seconds"] <= 0:

        raise ValueError(
            "poll_interval_seconds "
            "debe ser mayor que 0."
        )

    return config


# ============================================================
# VALIDAR DATAFRAME ESPECTRAL
# ============================================================

def validate_spectral_dataframe(
    dataframe,
    filename
):
    """
    Valida las columnas utilizadas por
    spectrum_latest.csv y waterfall.csv.
    """

    required_columns = [
        "timestamp",
        "frequency_offset_hz",
        "power_db",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:

        raise ValueError(
            f"Faltan columnas obligatorias "
            f"en {filename}: "
            f"{missing_columns}"
        )

    return dataframe


# ============================================================
# LEER ESPECTRO ACTUAL
# ============================================================

def load_spectrum():
    """
    Lee y valida spectrum_latest.csv.
    """

    spectrum = pd.read_csv(
        SPECTRUM_PATH
    )

    return validate_spectral_dataframe(
        spectrum,
        "spectrum_latest.csv"
    )


# ============================================================
# LEER WATERFALL
# ============================================================

def load_waterfall():
    """
    Lee y valida waterfall.csv.
    """

    waterfall = pd.read_csv(
        WATERFALL_PATH
    )

    return validate_spectral_dataframe(
        waterfall,
        "waterfall.csv"
    )


# ============================================================
# PRUEBA DEL MODULO
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # 1. CONFIGURACION SDR
    # --------------------------------------------------------

    sdr_config = load_sdr_config()

    print(
        "CONFIGURACION SDR LEIDA CORRECTAMENTE"
    )

    print(
        "------------------------------------"
    )

    print(
        f"Dispositivo: "
        f"{sdr_config['source_device']}"
    )

    print(
        f"Frecuencia central: "
        f"{sdr_config['center_frequency_hz']} Hz"
    )

    print(
        f"Sample rate: "
        f"{sdr_config['sample_rate_hz']} Hz"
    )

    print(
        f"Ganancia: "
        f"{sdr_config['gain_db']} dB"
    )

    print(
        f"FFT: "
        f"{sdr_config['fft_size']}"
    )

    print(
        f"Resolucion espectral: "
        f"{sdr_config['frequency_resolution_hz']} Hz"
    )

    # --------------------------------------------------------
    # 2. CONFIGURACION DETECTOR
    # --------------------------------------------------------

    detection_config = (
        load_detection_config()
    )

    print()

    print(
        "CONFIGURACION DETECTOR LEIDA CORRECTAMENTE"
    )

    print(
        "----------------------------------------"
    )

    print(
        f"Zona de exclusion heredada: "
        f"{detection_config['exclusion_hz']} Hz"
    )

    print(
        f"Notch referencia: "
        f"{detection_config['reference_notch_hz']} Hz"
    )

    print(
        f"Doppler minimo: "
        f"{detection_config['min_doppler_hz']} Hz"
    )

    print(
        f"Doppler maximo: "
        f"{detection_config['max_doppler_hz']} Hz"
    )

    print(
        f"Umbral: "
        f"{detection_config['threshold_db']} dB"
    )

    print(
        f"Persistencia minima: "
        f"{detection_config['minimum_hits']} hits"
    )

    print(
        f"Factor geometrico: "
        f"{detection_config['geometry_factor']}"
    )

    print(
        f"Intervalo de revision: "
        f"{detection_config['poll_interval_seconds']} s"
    )

    print(
        f"Estado: "
        f"{detection_config['status']}"
    )

    # --------------------------------------------------------
    # 3. ESPECTRO
    # --------------------------------------------------------

    spectrum = load_spectrum()

    print()

    print(
        "ESPECTRO LEIDO CORRECTAMENTE"
    )

    print(
        "----------------------------"
    )

    print(
        f"Cantidad de puntos: "
        f"{len(spectrum)}"
    )

    print(
        f"Offset minimo: "
        f"{spectrum['frequency_offset_hz'].min()} Hz"
    )

    print(
        f"Offset maximo: "
        f"{spectrum['frequency_offset_hz'].max()} Hz"
    )

    print(
        f"Potencia maxima: "
        f"{spectrum['power_db'].max()} dB"
    )

    # --------------------------------------------------------
    # 4. WATERFALL
    # --------------------------------------------------------

    waterfall = load_waterfall()

    print()

    print(
        "WATERFALL LEIDO CORRECTAMENTE"
    )

    print(
        "-----------------------------"
    )

    print(
        f"Cantidad total de registros: "
        f"{len(waterfall)}"
    )

    print(
        f"Cantidad de instantes: "
        f"{waterfall['timestamp'].nunique()}"
    )

    print(
        f"Offset minimo: "
        f"{waterfall['frequency_offset_hz'].min()} Hz"
    )

    print(
        f"Offset maximo: "
        f"{waterfall['frequency_offset_hz'].max()} Hz"
    )