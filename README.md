# Radar Doppler pasivo monocanal

Aplicación experimental con RTL-SDR, GNU Radio, Python y Streamlit para
capturar, analizar y visualizar actividad Doppler usando una emisora FM como
iluminador de oportunidad.

## Estructura principal

- `captures/`: archivo uniforme de capturas y resultados.
- `radar_app/`: componentes compartidos de la aplicación.
- `gnu_radio/`: flowgraphs y exportación de datos RF.
- `python_processing/`: detectores, métricas y pruebas.
- `streamlit_dashboard/`: interfaz de visualización.
- `docs/nueva_arquitectura.md`: etapas de integración de la aplicación.

## Ejecutar las pruebas

```powershell
python -m unittest discover -s python_processing/tests -v
```

## Abrir el dashboard

```powershell
streamlit run streamlit_dashboard/app.py
```
