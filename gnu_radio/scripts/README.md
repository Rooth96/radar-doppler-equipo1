# GNU Radio Scripts

Esta carpeta contiene scripts auxiliares asociados al módulo GNU Radio del Radar Doppler Pasivo Monocanal.

## Propósito

Los scripts de esta carpeta apoyarán la exportación de los datos generados por GNU Radio hacia los formatos definidos en el contrato de integración.

En la arquitectura nueva, GNU Radio deberá recibir la carpeta de la captura
activa y generar:

- `captures/<capture_id>/config/sdr_config.json`
- `captures/<capture_id>/raw/spectrum_latest.csv`
- `captures/<capture_id>/raw/waterfall.csv`

El flowgraph actual todavía escribe en `config/` y `data/realtime/`. La etapa 2
reemplazará esas rutas fijas por un directorio de salida recibido como parámetro.

## Formatos

### spectrum_latest.csv

Columnas:

timestamp,frequency_offset_hz,power_db

### waterfall.csv

Columnas:

timestamp,frequency_offset_hz,power_db

### sdr_config.json

Debe registrar como mínimo:

- timestamp
- center_frequency_hz
- sample_rate_hz
- gain_db
- fft_size
- frequency_resolution_hz
- window_type
- source_device

Todas las frecuencias se expresarán en Hz y la ganancia en dB.
