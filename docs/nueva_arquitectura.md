# Nueva arquitectura de capturas

## Objetivo

Eliminar el traspaso manual de archivos entre GNU Radio, el procesamiento en
Python y el dashboard. Una captura será la unidad de trabajo compartida por los
tres componentes.

## Flujo objetivo

```text
Dashboard -> administrador de capturas -> GNU Radio
                                            |
                                            v
                                      captures/<id>/raw
                                            |
                                            v
                                      procesamiento Python
                                            |
                                            v
                                   captures/<id>/processed
                                            |
                                            v
                                         Dashboard
```

## Etapa 1: almacenamiento y catálogo

- Existe un contrato uniforme documentado en `captures/README.md`.
- `radar_app.captures.CaptureRepository` crea, valida y descubre capturas.
- Los casos históricos están migrados al contrato uniforme.
- El dashboard construye su selector desde el catálogo y no desde rutas fijas.

Esta etapa se prueba sin hardware SDR.

## Etapa 2: adquisición y procesamiento

- El dashboard ya crea una captura con el nombre, tipo y notas indicados por el
  usuario.
- El modo simulado valida el recorrido completo: adquisición, datos originales,
  procesamiento, cambio de estados y visualización.
- Un orquestador iniciará el flowgraph exportado de GNU Radio como subproceso.
- El flowgraph recibe la captura activa mediante `RADAR_CAPTURE_DIR` y la
  duración mediante `RADAR_CAPTURE_DURATION_SECONDS`.
- La tasa de análisis es 24 kS/s y la FFT de 32768 puntos entrega una resolución
  aproximada de 0,732 Hz/bin para las bandas Doppler lentas.
- `RADAR_BASELINE_SECONDS` sincroniza el fondo: la ventana muestra una fase de
  reposo y luego avisa visual y sonoramente cuándo comenzar el movimiento.
- Al finalizar correctamente, el orquestador ejecutará el detector sobre esa
  misma captura y actualizará su estado.
- Solo podrá existir una adquisición activa a la vez.

La conexión del subproceso real y su prueba de integración requerirán el
RTL-SDR. El botón permanece deshabilitado hasta completar ese control.

## Etapa 3: operación robusta

- Inicio y detención controlados desde la interfaz.
- Progreso, registro de mensajes y errores visibles.
- Recuperación de capturas interrumpidas.
- Parámetros de adquisición y detección configurables desde el dashboard.
- Validación manual basada en lo observado, independiente de la predicción.
- Clasificación de cada ensayo como TP, TN, FP o FN y actualización de exactitud,
  tasa de detección y tasa de falsos positivos cuando exista ground truth.
