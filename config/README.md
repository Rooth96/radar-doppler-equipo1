# Configuración SDR

Esta carpeta contiene la configuración utilizada por el módulo GNU Radio.

El archivo generado durante la ejecución será:

- `sdr_config.json`

Campos obligatorios:

- timestamp
- center_frequency_hz
- sample_rate_hz
- gain_db
- fft_size
- frequency_resolution_hz
- window_type
- source_device

Las frecuencias se expresan en Hz y la ganancia en dB.

Los valores reales deberán provenir de la configuración y calibración efectivamente utilizada con el RTL-SDR/EQ-2.
