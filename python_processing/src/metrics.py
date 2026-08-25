from data_loader import load_sdr_config, load_spectrum
from signal_processing import (
    estimate_noise_floor,
    find_reference_carrier,
    find_doppler_candidate,
)


SPEED_OF_LIGHT_MPS = 299792458.0


def calculate_doppler_hz(candidate_frequency_hz, reference_offset_hz):
    """
    Calcula el desplazamiento Doppler respecto de la
    referencia observada.
    """

    return float(
        candidate_frequency_hz - reference_offset_hz
    )


def calculate_snr_db(peak_power_db, noise_floor_db):
    """
    Calcula el SNR en dB.
    """

    return float(
        peak_power_db - noise_floor_db
    )


def calculate_wavelength_m(center_frequency_hz):
    """
    Calcula la longitud de onda:
    lambda = c / f
    """

    if center_frequency_hz <= 0:
        raise ValueError(
            "La frecuencia central debe ser mayor que cero."
        )

    return float(
        SPEED_OF_LIGHT_MPS / center_frequency_hz
    )


def estimate_velocity_kmh(
    doppler_hz,
    wavelength_m,
    geometry_factor,
):
    """
    Estima la velocidad relativa a partir del Doppler.

    fd = (v / lambda) * geometry_factor

    Por lo tanto:

    v = fd * lambda / geometry_factor

    geometry_factor depende de la geometria biestatica
    y de la direccion de movimiento del blanco.

    La velocidad obtenida es una ESTIMACION.
    """

    if geometry_factor <= 0 or geometry_factor > 2:
        raise ValueError(
            "geometry_factor debe estar entre 0 y 2."
        )

    velocity_mps = (
        abs(doppler_hz)
        * wavelength_m
        / geometry_factor
    )

    velocity_kmh = velocity_mps * 3.6

    return float(velocity_kmh)


if __name__ == "__main__":

    config = load_sdr_config()
    spectrum = load_spectrum()

    noise_floor_db = estimate_noise_floor(
        spectrum,
        central_exclusion_hz=50.0
    )

    reference_offset_hz, reference_power_db = find_reference_carrier(
        spectrum,
        search_range_hz=50.0
    )

    candidate = find_doppler_candidate(
        spectrum=spectrum,
        reference_offset_hz=reference_offset_hz,
        noise_floor_db=noise_floor_db,
        exclusion_hz=50.0,
        threshold_db=8.0,
    )

    print("METRICAS DOPPLER")
    print("----------------")

    if candidate is None:
        print("No existe candidato Doppler.")

    else:

        doppler_hz = calculate_doppler_hz(
            candidate["frequency_hz"],
            reference_offset_hz
        )

        snr_db = calculate_snr_db(
            candidate["power_db"],
            noise_floor_db
        )

        wavelength_m = calculate_wavelength_m(
            config["center_frequency_hz"]
        )

        # Valor PROVISIONAL para desarrollo.
        # Debe ajustarse segun la geometria real de la prueba.
        geometry_factor = 2.0

        velocity_est_kmh = estimate_velocity_kmh(
            doppler_hz,
            wavelength_m,
            geometry_factor
        )

        print(
            f"Frecuencia central: "
            f"{config['center_frequency_hz']} Hz"
        )

        print(
            f"Longitud de onda: "
            f"{wavelength_m:.4f} m"
        )

        print(
            f"Frecuencia de referencia: "
            f"{reference_offset_hz:.2f} Hz"
        )

        print(
            f"Frecuencia candidata: "
            f"{candidate['frequency_hz']:.2f} Hz"
        )

        print(
            f"Doppler estimado: "
            f"{doppler_hz:.2f} Hz"
        )

        print(
            f"SNR estimado: "
            f"{snr_db:.2f} dB"
        )

        print(
            f"Factor geometrico provisional: "
            f"{geometry_factor:.2f}"
        )

        print(
            f"Velocidad relativa estimada: "
            f"{velocity_est_kmh:.2f} km/h"
        )