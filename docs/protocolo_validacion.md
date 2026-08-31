# Protocolo de validación experimental

## Objetivo inicial

Medir el comportamiento del perfil `human` con una serie mínima de diez ensayos:

- cinco capturas de referencia sin movimiento;
- cinco capturas con movimiento de una persona u objeto;
- 25 segundos por captura;
- 10 segundos iniciales de reposo para construir el baseline;
- misma posición de antenas, frecuencia, ganancia y entorno.

## Procedimiento por ensayo

1. Crear una captura con un nombre único y seleccionar el perfil correcto.
2. Iniciar el RTL-SDR desde el dashboard.
3. Mantener reposo mientras la ventana indique `FASE 1`.
4. En ensayos positivos, comenzar el movimiento únicamente cuando la ventana
   indique `FASE 2`. En ensayos negativos, mantener reposo hasta el cierre.
5. Revisar el resultado automático y registrar lo realmente observado usando
   uno de los dos botones de validación.
6. Verificar que el ensayo aparezca en el resumen global.

## Interpretación

- `TP`: el sistema detectó movimiento y este fue observado.
- `TN`: el sistema indicó reposo y no se observó movimiento.
- `FP`: el sistema detectó movimiento, pero el escenario permaneció en reposo.
- `FN`: hubo movimiento observado, pero el sistema no lo detectó.

No deben ajustarse parámetros después de cada captura individual. Los cambios de
umbral, bins o persistencia se decidirán al finalizar la serie completa para
evitar calibrar el detector contra un único ejemplo.
