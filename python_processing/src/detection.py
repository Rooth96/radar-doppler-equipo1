from data_loader import (
    load_detection_config,
    load_spectrum,
    load_waterfall,
)

from signal_processing import (
    estimate_noise_floor,
    find_reference_carrier,
    suppress_reference_notch,
    find_doppler_candidate,
)

from metrics import (
    calculate_doppler_hz,
    calculate_snr_db,
)


# ============================================================
# COMPROBAR PERSISTENCIA TEMPORAL
# ============================================================

def check_persistence(
    waterfall,
    candidate_frequency_hz,
    noise_floor_db,
    threshold_db,
    minimum_hits,
):
    """
    Comprueba si la energia asociada al candidato
    aparece persistentemente en varios instantes
    del waterfall.
    """

    timestamps = waterfall[
        "timestamp"
    ].unique()

    hits = 0

    minimum_power_db = (
        noise_floor_db
        + threshold_db
    )

    for timestamp in timestamps:

        current = waterfall[
            waterfall["timestamp"]
            == timestamp
        ]

        distances = (
            current["frequency_offset_hz"]
            - candidate_frequency_hz
        ).abs()

        nearest_index = (
            distances.idxmin()
        )

        nearest_power_db = float(
            current.loc[
                nearest_index,
                "power_db"
            ]
        )

        if (
            nearest_power_db
            >= minimum_power_db
        ):
            hits += 1

    persistent = (
        hits >= minimum_hits
    )

    return (
        persistent,
        hits,
        len(timestamps)
    )


# ============================================================
# LOGICA PRINCIPAL DE DETECCION
# ============================================================

def detect_movement(
    spectrum,
    waterfall,
    exclusion_hz,
    threshold_db,
    minimum_hits,
):
    """
    Ejecuta la logica completa de deteccion Doppler.

    Flujo:

    1. Estimar piso de ruido.
    2. Detectar referencia.
    3. Suprimir componente estacionaria.
    4. Buscar candidato Doppler.
    5. Calcular Doppler.
    6. Calcular SNR.
    7. Comprobar persistencia.
    8. Determinar detected.
    """

    # --------------------------------------------------------
    # 1. Piso de ruido
    # --------------------------------------------------------

    noise_floor_db = estimate_noise_floor(
        spectrum,
        central_exclusion_hz=exclusion_hz
    )

    # --------------------------------------------------------
    # 2. Referencia / portadora
    # --------------------------------------------------------

    (
        reference_offset_hz,
        reference_power_db
    ) = find_reference_carrier(
        spectrum,
        search_range_hz=exclusion_hz
    )

    # --------------------------------------------------------
    # 3. Supresion de componente estacionaria
    # --------------------------------------------------------

    suppressed_spectrum = suppress_reference_notch(
        spectrum=spectrum,
        reference_offset_hz=reference_offset_hz,
        noise_floor_db=noise_floor_db,
        notch_half_width_hz=exclusion_hz,
    )

    # --------------------------------------------------------
    # 4. Buscar candidato Doppler
    # --------------------------------------------------------

    candidate = find_doppler_candidate(
        spectrum=suppressed_spectrum,
        reference_offset_hz=reference_offset_hz,
        noise_floor_db=noise_floor_db,
        exclusion_hz=exclusion_hz,
        threshold_db=threshold_db,
        power_column="power_suppressed_db",
    )

    # --------------------------------------------------------
    # 5. Caso SIN candidato
    # --------------------------------------------------------

    if candidate is None:

        return {
            "detected": False,
            "doppler_hz": 0.0,
            "snr_db": 0.0,
            "peak_power_db": float(
                noise_floor_db
            ),
            "noise_floor_db": float(
                noise_floor_db
            ),
            "reference_offset_hz": float(
                reference_offset_hz
            ),
            "reference_power_db": float(
                reference_power_db
            ),
            "candidate_frequency_hz": 0.0,
            "persistence_hits": 0,
            "total_instants": int(
                waterfall[
                    "timestamp"
                ].nunique()
            ),
        }

    # --------------------------------------------------------
    # 6. Doppler
    # --------------------------------------------------------

    doppler_hz = calculate_doppler_hz(
        candidate["frequency_hz"],
        reference_offset_hz
    )

    # --------------------------------------------------------
    # 7. SNR
    # --------------------------------------------------------

    snr_db = calculate_snr_db(
        candidate["power_db"],
        noise_floor_db
    )

    # --------------------------------------------------------
    # 8. Persistencia
    # --------------------------------------------------------

    (
        persistent,
        hits,
        total_instants
    ) = check_persistence(
        waterfall=waterfall,
        candidate_frequency_hz=(
            candidate["frequency_hz"]
        ),
        noise_floor_db=noise_floor_db,
        threshold_db=threshold_db,
        minimum_hits=minimum_hits,
    )

    # --------------------------------------------------------
    # 9. Decision final
    # --------------------------------------------------------

    detected = (
        snr_db >= threshold_db
        and persistent
    )

    # --------------------------------------------------------
    # 10. Resultado completo
    # --------------------------------------------------------

    return {
        "detected": bool(
            detected
        ),
        "doppler_hz": float(
            doppler_hz
        ),
        "snr_db": float(
            snr_db
        ),
        "peak_power_db": float(
            candidate["power_db"]
        ),
        "noise_floor_db": float(
            noise_floor_db
        ),
        "reference_offset_hz": float(
            reference_offset_hz
        ),
        "reference_power_db": float(
            reference_power_db
        ),
        "candidate_frequency_hz": float(
            candidate["frequency_hz"]
        ),
        "persistence_hits": int(
            hits
        ),
        "total_instants": int(
            total_instants
        ),
    }


# ============================================================
# PRUEBA DEL MODULO
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # 1. Leer datos
    # --------------------------------------------------------

    spectrum = load_spectrum()
    waterfall = load_waterfall()

    # --------------------------------------------------------
    # 2. Leer parametros configurables
    # --------------------------------------------------------

    detection_config = (
        load_detection_config()
    )

    exclusion_hz = float(
        detection_config[
            "exclusion_hz"
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

    # --------------------------------------------------------
    # 3. Ejecutar detector
    # --------------------------------------------------------

    result = detect_movement(
        spectrum=spectrum,
        waterfall=waterfall,
        exclusion_hz=exclusion_hz,
        threshold_db=threshold_db,
        minimum_hits=minimum_hits,
    )

    # ========================================================
    # RESULTADOS
    # ========================================================

    print(
        "DETECCION DOPPLER CON CONFIGURACION"
    )

    print(
        "----------------------------------"
    )

    print(
        f"Zona de exclusion: "
        f"{exclusion_hz:.2f} Hz"
    )

    print(
        f"Umbral: "
        f"{threshold_db:.2f} dB"
    )

    print(
        f"Persistencia minima: "
        f"{minimum_hits} hits"
    )

    print()

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
        f"Persistencia: "
        f"{result['persistence_hits']} / "
        f"{result['total_instants']} "
        f"instantes"
    )