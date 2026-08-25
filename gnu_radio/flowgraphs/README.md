# GNU Radio Flowgraphs

Esta carpeta contiene los flowgraphs de GNU Radio utilizados para la adquisición y preprocesamiento de señales RF del Radar Doppler Pasivo Monocanal del Equipo 1.

## Flowgraph principal

- `radar_capture.grc`

## Hardware objetivo

- RTL-SDR / EQ-2
- RTL2832U + R820T2
- Solo recepción (RX)

## Responsabilidad del módulo

- Sintonización de la emisora FM.
- Configuración de frecuencia central.
- Configuración de sample rate.
- Configuración de ganancia.
- Generación de FFT y waterfall.
- Exportación de datos hacia el módulo de procesamiento en Python.
