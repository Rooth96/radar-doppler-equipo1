# Caso 02 — vehículo objetivo a 30 km/h

## Alcance

Este caso utiliza un flowgraph independiente:

- `gnu_radio/flowgraphs/radar_vehicle_30kmh.grc`

El flowgraph estable `gnu_radio/flowgraphs/radar_capture.grc` no se modifica.

## Salidas de GNU Radio

La ejecución crea o actualiza exactamente estos tres archivos dentro de la carpeta del caso:

- `caso_02_vehiculo_30kmh/config/sdr_config.json`
- `caso_02_vehiculo_30kmh/data/realtime/spectrum_latest.csv`
- `caso_02_vehiculo_30kmh/data/realtime/waterfall.csv`

Los dos CSV conservan el contrato acordado:

```text
timestamp,frequency_offset_hz,power_db
```

`sdr_config.json` conserva todos los campos obligatorios del contrato y agrega metadatos del escenario vehicular.

## Fundamento de la configuración

Para una estación de referencia de 99,3 MHz y un vehículo a 30 km/h, el desplazamiento Doppler máximo teórico es:

```text
fd_max = 2 * v * f0 / c ≈ 5,52 Hz
```

El valor real puede ser menor porque depende del ángulo y de la geometría biestática. Por esta razón, el vehículo no debe pasar en una trayectoria puramente transversal respecto de la dirección efectiva de observación.

La cadena operacional del caso es:

1. RTL-SDR Source.
2. Frequency Xlating FIR Filter para centrar la estación de referencia.
3. Complex to Mag^2 para obtener el batido de movimiento.
4. Dos filtros y decimaciones hasta 200 muestras/s.
5. DC Blocker.
6. Exportador espectral vehicular.

La FFT es de 1024 puntos a 200 muestras/s, con resolución de 0,1953125 Hz/bin y una ventana temporal de 5,12 s. Solo se exporta el intervalo de -20 a +20 Hz.

## Ajuste que requiere el módulo Python

El detector general actualmente configurado para 15–150 Hz no puede detectar un vehículo objetivo a 30 km/h en 99,3 MHz. Para este caso, el integrante responsable de Python debe leer la carpeta `caso_02_vehiculo_30kmh` y calibrar experimentalmente un rango inicial cercano a:

- `reference_notch_hz`: 1 Hz.
- `min_doppler_hz`: 1 Hz.
- `max_doppler_hz`: 10 Hz.
- `exclusion_hz`: 10 Hz, para estimar el ruido dentro del espectro exportado de ±20 Hz.
- `geometry_factor`: calibrado según la disposición real; no debe suponerse automáticamente igual a 2.

El umbral, la persistencia y la ganancia del SDR deben ajustarse con una medición de reposo y varias pasadas reales.

## Procedimiento de prueba

1. Abrir `radar_vehicle_30kmh.grc` en GNU Radio Companion.
2. Confirmar la frecuencia real de la emisora, el `tune_offset` y una ganancia sin saturación.
3. Ejecutar al menos 10 s sin vehículo para observar el fondo.
4. Hacer pasar el vehículo a 30 km/h con componente de movimiento hacia o desde la antena.
5. Mantener el flowgraph ejecutándose al menos 10 s después de la pasada.
6. Verificar que los tres archivos del caso se hayan actualizado y entregar esa carpeta al integrante de Python.

## Limitación experimental

Este montaje monocanal no separa una referencia y una vigilancia independientes ni realiza cancelación adaptativa de la señal directa. La velocidad obtenida debe presentarse como estimación experimental y validarse contra la velocidad conocida del vehículo.
