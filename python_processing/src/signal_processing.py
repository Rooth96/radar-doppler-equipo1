from scipy.signal import find_peaks

from data_loader import load_spectrum


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

    El parametro central_exclusion_hz es provisional
    y debe ajustarse durante la calibracion real.
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
    notch_half_width_hz=50.0
):
    """
    Aplica una supresion espectral tipo notch
    alrededor de la referencia observada.

    No modifica el archivo original.

    Crea una nueva columna:
    power_suppressed_db

    Dentro de la zona del notch, la componente
    estacionaria se lleva provisionalmente al
    nivel estimado del piso de ruido.

    Este procedimiento sirve para el procesamiento
    del detector.

    La atenuacion obtenida aqui es una medida
    SOFTWARE y NO corresponde directamente a la
    atenuacion fisica de geometria exigida en
    la evaluacion.
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
    ] = float(noise_floor_db)

    return processed


# ============================================================
# ATENUACION DE SOFTWARE DEL NOTCH
# ============================================================

def calculate_software_notch_attenuation(
    original_reference_power_db,
    suppressed_reference_power_db
):
    """
    Calcula cuanto redujo el software la componente
    de referencia.

    IMPORTANTE:
    Este valor es solo diagnostico del procesamiento.

    NO debe utilizarse todavia como
    carrier_attenuation_db oficial de geometria.
    """

    attenuation_db = (
        original_reference_power_db
        - suppressed_reference_power_db
    )

    return float(attenuation_db)


# ============================================================
# BUSQUEDA DE CANDIDATO DOPPLER
# ============================================================

def find_doppler_candidate(
    spectrum,
    reference_offset_hz,
    noise_floor_db,
    exclusion_hz=50.0,
    threshold_db=8.0,
    power_column="power_db",
):
    """
    Busca picos fuera de la zona central y sobre
    un umbral relativo al piso de ruido.

    power_column permite trabajar con:
    - power_db
    - power_suppressed_db

    segun la etapa del procesamiento.
    """

    if power_column not in spectrum.columns:
        raise ValueError(
            f"No existe la columna {power_column}"
        )

    spectrum_sorted = (
        spectrum
        .sort_values("frequency_offset_hz")
        .reset_index(drop=True)
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

    minimum_power_db = (
        noise_floor_db
        + threshold_db
    )

    peak_indices, _ = find_peaks(
        powers,
        height=minimum_power_db
    )

    candidates = []

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
            > exclusion_hz
        ):

            candidates.append(
                {
                    "frequency_hz": frequency_hz,
                    "power_db": power_db,
                }
            )

    if not candidates:
        return None

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
    # 1. Leer espectro
    # --------------------------------------------------------

    spectrum = load_spectrum()

    # --------------------------------------------------------
    # 2. Estimar ruido
    # --------------------------------------------------------

    noise_floor_db = estimate_noise_floor(
        spectrum,
        central_exclusion_hz=50.0
    )

    # --------------------------------------------------------
    # 3. Encontrar referencia
    # --------------------------------------------------------

    (
        reference_offset_hz,
        reference_power_db
    ) = find_reference_carrier(
        spectrum,
        search_range_hz=50.0
    )

    # --------------------------------------------------------
    # 4. Aplicar notch espectral
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
            notch_half_width_hz=50.0,
        )
    )

    # --------------------------------------------------------
    # 5. Localizar referencia luego del notch
    # --------------------------------------------------------

    reference_row = (
        suppressed_spectrum[
            (
                suppressed_spectrum[
                    "frequency_offset_hz"
                ]
                - reference_offset_hz
            ).abs()
            ==
            (
                suppressed_spectrum[
                    "frequency_offset_hz"
                ]
                - reference_offset_hz
            ).abs().min()
        ]
        .iloc[0]
    )

    suppressed_reference_power_db = float(
        reference_row[
            "power_suppressed_db"
        ]
    )

    # --------------------------------------------------------
    # 6. Calcular atenuacion SOFTWARE
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
    # 7. Buscar candidato usando espectro suprimido
    # --------------------------------------------------------

    candidate = find_doppler_candidate(
        spectrum=suppressed_spectrum,
        reference_offset_hz=(
            reference_offset_hz
        ),
        noise_floor_db=(
            noise_floor_db
        ),
        exclusion_hz=50.0,
        threshold_db=8.0,
        power_column="power_suppressed_db",
    )

    # ========================================================
    # RESULTADOS
    # ========================================================

    print(
        "SUPRESION DE COMPONENTE ESTACIONARIA"
    )

    print(
        "-----------------------------------"
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
        "CANDIDATO DESPUES DE SUPRESION"
    )

    print(
        "-------------------------------"
    )

    if candidate is None:

        print(
            "No se encontro candidato Doppler."
        )

    else:

        print(
            f"Frecuencia candidata: "
            f"{candidate['frequency_hz']:.2f} Hz"
        )

        print(
            f"Potencia candidata: "
            f"{candidate['power_db']:.2f} dB"
        )