# Capturas experimentales

Esta carpeta es el archivo único de experimentos del sistema. Cada subcarpeta
representa una captura independiente y conserva tanto los datos originales como
los resultados derivados.

## Contrato de una captura

```text
captures/<capture_id>/
├── metadata.json
├── config/
│   ├── sdr_config.json
│   └── detection_config.json
├── raw/
│   ├── spectrum_latest.csv
│   └── waterfall.csv
└── processed/
    ├── detection_latest.json
    ├── events.csv
    ├── metrics.json
    └── ground_truth.csv       # se crea al validar, si corresponde
```

`raw/` es evidencia inmutable de lo generado por GNU Radio. El procesamiento
puede volver a ejecutarse y reemplazar los archivos derivados de `processed/`,
pero nunca debe modificar los archivos originales de `raw/`.

## Metadatos

`metadata.json` identifica la captura sin depender del nombre de su carpeta.
Los campos obligatorios de la versión 1 son:

- `schema_version`: versión del contrato; actualmente `1`.
- `capture_id`: identificador único, igual al nombre de la carpeta.
- `name`: nombre editable y visible para el usuario.
- `kind`: `baseline`, `human`, `vehicle` o `unknown`.
- `status`: `created`, `capturing`, `captured`, `processing`, `completed` o
  `failed`. `captured` indica que los datos RF están guardados pero todavía no
  han sido procesados.
- `created_at`: fecha y hora ISO 8601 con zona horaria.
- `notes`: observaciones opcionales.
- `expected_movement`: condición prevista por el protocolo al crear el ensayo.
- `acquisition_mode`, `requested_duration_seconds` y `baseline_seconds`: se
  agregan al comenzar una adquisición real.

El dashboard descubre automáticamente cualquier captura válida guardada aquí.
