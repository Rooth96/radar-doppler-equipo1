from scipy.signal import find_peaks

from data_loader import (
    load_detection_config,
    load_spectrum,
)


# ============================================================
# ESTIMACION DEL PISO DE RUIDO
# ============================================================

def estimate_noise_floor(
    spectrum,
    central_exclusion_hz=50.0
):
    """
    Estima el piso de ruido mediante la mediana de la potencia
    fuera de una zona central de exclusion.
    """

    noise_region = spectrum[
        spectrum["frequency_offset_hz"].abs()
        > central_exclusion_hz
    ]

    if noise_region.empty:

        raise ValueError(
            "No existen suficientes puntos fuera de la "
            "zona central para estimar el piso de ruido."
        )

    noise_floor_db = (
        noise_region["power_db"].median()
    )

    return float(noise_floor_db)


# ============================================================
# BUSQUEDA DE LA REFERENCIA / PORTADORA
# ============================================================

def find_reference_carrier(
    spectrum,
    search_range_hz=50.0
):
    """
    Busca la componente de mayor potencia dentro
    de una region cercana al centro del espectro.

    Retorna:
    - offset observado de la referencia en Hz
    - potencia de la referencia en dB
    """

    central_region = spectrum[
        spectrum["frequency_offset_hz"].abs()
        <= search_range_hz
    ]

    if central_region.empty:

        raise ValueError(
            "No existen puntos dentro de la zona "
            "de busqueda de la referencia."
        )

    max_index = (
        central_region["power_db"].idxmax()
    )

    reference_offset_hz = (
        central_region.loc[
            max_index,
            "frequency_offset_hz"
        ]
    )

    reference_power_db = (
        central_region.loc[
            max_index,
            "power_db"
        ]
    )

    return (
        float(reference_offset_hz),
        float(reference_power_db)
    )


# ============================================================
# SUPRESION DE LA COMPONENTE ESTACIONARIA
# ============================================================

def suppress_reference_notch(
    spectrum,
    reference_offset_hz,
    noise_floor_db,
    notch_half_width_hz=15.0
):
    """
    Aplica una supresion espectral tipo notch
    alrededor de la referencia observada.

    No modifica el archivo original.

    Crea una nueva columna:
    power_suppressed_db

    IMPORTANTE:
    Esta supresion es SOFTWARE.
    No representa directamente la atenuacion
    fisica exigida experimentalmente.
    """

    processed = spectrum.copy()

    processed["power_suppressed_db"] = (
        processed["power_db"].astype(float)
    )

    distance_from_reference = (
        processed["frequency_offset_hz"]
        - reference_offset_hz
    ).abs()

    notch_mask = (
        distance_from_reference
        <= notch_half_width_hz
    )

    processed.loc[
        notch_mask,
        "power_suppressed_db"
    ] = float(
        noise_floor_db
    )

    return processed


# ============================================================
# ATENUACION SOFTWARE DEL NOTCH
# ============================================================

def calculate_software_notch_attenuation(
    original_reference_power_db,
    suppressed_reference_power_db
):
    """
    Calcula cuanto redujo el software
    la componente de referencia.

    Este valor es diagnostico del procesamiento
    y no debe confundirse con la atenuacion
    fisica de la portadora directa.
    """

    attenuation_db = (
        original_reference_power_db
        - suppressed_reference_power_db
    )

    return float(
        attenuation_db
    )


# ============================================================
# BUSQUEDA DE CANDIDATO DOPPLER
# ============================================================

def find_doppler_candidate(
    spectrum,
    reference_offset_hz,
    noise_floor_db,
    min_doppler_hz=15.0,
    max_doppler_hz=150.0,
    threshold_db=8.0,
    power_column="power_db",
    exclusion_hz=None,
):
    """
    Busca picos sobre el umbral de potencia
    dentro de una zona Doppler fisicamente
    acotada respecto de la referencia.

    Un candidato debe cumplir:

    min_doppler_hz <= |f - f_ref| <= max_doppler_hz

    exclusion_hz se conserva temporalmente
    por compatibilidad con las pruebas anteriores.
    """

    if power_column not in spectrum.columns:

        raise ValueError(
            f"No existe la columna {power_column}"
        )

    # --------------------------------------------------------
    # COMPATIBILIDAD CON VERSION ANTERIOR
    # --------------------------------------------------------

    if exclusion_hz is not None:

        min_doppler_hz = float(
            exclusion_hz
        )

    if min_doppler_hz <= 0:

        raise ValueError(
            "min_doppler_hz debe ser mayor que 0."
        )

    if max_doppler_hz <= min_doppler_hz:

        raise ValueError(
            "max_doppler_hz debe ser mayor "
            "que min_doppler_hz."
        )

    # --------------------------------------------------------
    # ORDENAR ESPECTRO
    # --------------------------------------------------------

    spectrum_sorted = (
        spectrum
        .sort_values(
            "frequency_offset_hz"
        )
        .reset_index(
            drop=True
        )
    )

    frequencies = (
        spectrum_sorted[
            "frequency_offset_hz"
        ].to_numpy()
    )

    powers = (
        spectrum_sorted[
            power_column
        ].to_numpy()
    )

    # --------------------------------------------------------
    # UMBRAL DE POTENCIA
    # --------------------------------------------------------

    minimum_power_db = (
        noise_floor_db
        + threshold_db
    )

    peak_indices, _ = find_peaks(
        powers,
        height=minimum_power_db
    )

    candidates = []

    # --------------------------------------------------------
    # FILTRAR POR RANGO DOPPLER
    # --------------------------------------------------------

    for index in peak_indices:

        frequency_hz = float(
            frequencies[index]
        )

        power_db = float(
            powers[index]
        )

        distance_from_reference = abs(
            frequency_hz
            - reference_offset_hz
        )

        if (
            distance_from_reference
            >= min_doppler_hz
            and
            distance_from_reference
            <= max_doppler_hz
        ):

            candidates.append(
                {
                    "frequency_hz":
                        frequency_hz,

                    "power_db":
                        power_db,

                    "doppler_distance_hz":
                        float(
                            distance_from_reference
                        ),
                }
            )

    # --------------------------------------------------------
    # SIN CANDIDATOS
    # --------------------------------------------------------

    if not candidates:

        return None

    # --------------------------------------------------------
    # SELECCIONAR EL MAS POTENTE
    # --------------------------------------------------------

    strongest_candidate = max(
        candidates,
        key=lambda candidate:
        candidate["power_db"]
    )

    return strongest_candidate


# ============================================================
# PRUEBA DEL MODULO
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # 1. LEER CONFIGURACION
    # --------------------------------------------------------

    detection_config = (
        load_detection_config()
    )

    reference_search_hz = float(
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

    # --------------------------------------------------------
    # 2. LEER ESPECTRO
    # --------------------------------------------------------

    spectrum = (
        load_spectrum()
    )

    # --------------------------------------------------------
    # 3. ESTIMAR RUIDO
    # --------------------------------------------------------

    noise_floor_db = (
        estimate_noise_floor(
            spectrum,
            central_exclusion_hz=(
                reference_search_hz
            )
        )
    )

    # --------------------------------------------------------
    # 4. ENCONTRAR REFERENCIA
    # --------------------------------------------------------

    (
        reference_offset_hz,
        reference_power_db
    ) = find_reference_carrier(
        spectrum,
        search_range_hz=(
            reference_search_hz
        )
    )

    # --------------------------------------------------------
    # 5. APLICAR NOTCH
    # --------------------------------------------------------

    suppressed_spectrum = (
        suppress_reference_notch(
            spectrum=spectrum,

            reference_offset_hz=(
                reference_offset_hz
            ),

            noise_floor_db=(
                noise_floor_db
            ),

            notch_half_width_hz=(
                reference_notch_hz
            ),
        )
    )

    # --------------------------------------------------------
    # 6. POTENCIA DESPUES DEL NOTCH
    # --------------------------------------------------------

    distance_to_reference = (
        suppressed_spectrum[
            "frequency_offset_hz"
        ]
        - reference_offset_hz
    ).abs()

    nearest_index = (
        distance_to_reference.idxmin()
    )

    suppressed_reference_power_db = float(
        suppressed_spectrum.loc[
            nearest_index,
            "power_suppressed_db"
        ]
    )

    # --------------------------------------------------------
    # 7. ATENUACION SOFTWARE
    # --------------------------------------------------------

    software_attenuation_db = (
        calculate_software_notch_attenuation(
            original_reference_power_db=(
                reference_power_db
            ),

            suppressed_reference_power_db=(
                suppressed_reference_power_db
            ),
        )
    )

    # --------------------------------------------------------
    # 8. BUSCAR CANDIDATO DOPPLER
    # --------------------------------------------------------

    candidate = (
        find_doppler_candidate(
            spectrum=(
                suppressed_spectrum
            ),

            reference_offset_hz=(
                reference_offset_hz
            ),

            noise_floor_db=(
                noise_floor_db
            ),

            min_doppler_hz=(
                min_doppler_hz
            ),

            max_doppler_hz=(
                max_doppler_hz
            ),

            threshold_db=(
                threshold_db
            ),

            power_column=(
                "power_suppressed_db"
            ),
        )
    )

    # ========================================================
    # RESULTADOS
    # ========================================================

    print(
        "PROCESAMIENTO ESPECTRAL "
        "CON RANGO DOPPLER"
    )

    print(
        "------------------------------------"
    )

    print(
        f"Piso de ruido: "
        f"{noise_floor_db:.2f} dB"
    )

    print(
        f"Referencia observada: "
        f"{reference_offset_hz:.2f} Hz"
    )

    print(
        f"Potencia referencia antes: "
        f"{reference_power_db:.2f} dB"
    )

    print(
        f"Potencia referencia despues: "
        f"{suppressed_reference_power_db:.2f} dB"
    )

    print(
        f"Atenuacion SOFTWARE del notch: "
        f"{software_attenuation_db:.2f} dB"
    )

    print()

    print(
        "PARAMETROS DE BUSQUEDA DOPPLER"
    )

    print(
        "------------------------------------"
    )

    print(
        f"Notch referencia: "
        f"{reference_notch_hz:.2f} Hz"
    )

    print(
        f"Doppler minimo: "
        f"{min_doppler_hz:.2f} Hz"
    )

    print(
        f"Doppler maximo: "
        f"{max_doppler_hz:.2f} Hz"
    )

    print(
        f"Umbral: "
        f"{threshold_db:.2f} dB"
    )

    print()

    print(
        "CANDIDATO DENTRO DEL RANGO DOPPLER"
    )

    print(
        "------------------------------------"
    )

    if candidate is None:

        print(
            "No se encontro candidato "
            "Doppler dentro del rango."
        )

    else:

        print(
            f"Frecuencia candidata: "
            f"{candidate['frequency_hz']:.2f} Hz"
        )

        print(
            f"Separacion respecto referencia: "
            f"{candidate['doppler_distance_hz']:.2f} Hz"
        )

        print(
            f"Potencia candidata: "
            f"{candidate['power_db']:.2f} dB"
        )