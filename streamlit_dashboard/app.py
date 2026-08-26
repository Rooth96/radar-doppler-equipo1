
from pathlib import Path
import json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================
st.set_page_config(
    page_title="Radar Doppler Pasivo - Equipo 1",
    page_icon="📡",
    layout="wide"
)

# app.py debe quedar en /streamlit_dashboard.
# BASE_DIR apunta a la raíz del proyecto completo.
BASE_DIR = Path(__file__).resolve().parent.parent

CASE_NAME = "CASO 1 — SIN VEHÍCULO"
CASE_DIR = BASE_DIR / "caso_01_sin_vehiculo"

CONFIG_FILE = CASE_DIR / "config" / "sdr_config.json"
DETECTION_CONFIG_FILE = CASE_DIR / "config" / "detection_config.json"
SPECTRUM_FILE = CASE_DIR / "data" / "realtime" / "spectrum_latest.csv"
WATERFALL_FILE = CASE_DIR / "data" / "realtime" / "waterfall.csv"
EVENTS_FILE = CASE_DIR / "data" / "processed" / "events.csv"
METRICS_FILE = CASE_DIR / "data" / "processed" / "metrics.json"
DETECTION_FILE = CASE_DIR / "data" / "processed" / "detection_latest.json"
GROUND_TRUTH_FILE = CASE_DIR / "data" / "processed" / "ground_truth.csv"

# ==========================================================
# FUNCIONES DE LECTURA
# ==========================================================
def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_csv(path):
    return pd.read_csv(path)

def hz_to_mhz(value):
    return value / 1_000_000

def hz_to_msps(value):
    return value / 1_000_000

def ensure_ground_truth_file():
    if not GROUND_TRUTH_FILE.exists():
        pd.DataFrame(
            columns=["timestamp", "event_id", "ground_truth", "validation_type"]
        ).to_csv(GROUND_TRUTH_FILE, index=False)

def save_validation(timestamp, event_id, ground_truth, validation_type):
    ensure_ground_truth_file()
    current = pd.read_csv(GROUND_TRUTH_FILE)
    new_row = pd.DataFrame([{
        "timestamp": timestamp,
        "event_id": event_id,
        "ground_truth": ground_truth,
        "validation_type": validation_type
    }])
    current = pd.concat([current, new_row], ignore_index=True)
    current.to_csv(GROUND_TRUTH_FILE, index=False)

# ==========================================================
# CARGA DE DATOS
# ==========================================================
try:
    sdr_config = read_json(CONFIG_FILE)
    detection_config = read_json(DETECTION_CONFIG_FILE)
    spectrum = read_csv(SPECTRUM_FILE)
    waterfall = read_csv(WATERFALL_FILE)
    events = read_csv(EVENTS_FILE)
    metrics = read_json(METRICS_FILE)
    detection = read_json(DETECTION_FILE)
    ensure_ground_truth_file()
except Exception as e:
    st.error(f"No se pudieron cargar los archivos de entrada: {e}")
    st.stop()

# Normalización básica
events["detected"] = events["detected"].astype(str).str.lower().map({"true": True, "false": False}).fillna(events["detected"])
waterfall["timestamp"] = pd.to_datetime(waterfall["timestamp"])
spectrum["timestamp"] = pd.to_datetime(spectrum["timestamp"])
events["timestamp"] = pd.to_datetime(events["timestamp"])

# ==========================================================
# ENCABEZADO
# ==========================================================
st.title("📡 Radar Doppler Pasivo Monocanal")
st.caption("Equipo 1 — Dashboard de visualización y explotación de resultados")
st.info(f"Experimento analizado: **{CASE_NAME}**")

# ==========================================================
# ESTADO DEL SDR
# ==========================================================
st.subheader("Estado del sistema")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Frecuencia central", f"{hz_to_mhz(sdr_config['center_frequency_hz']):.3f} MHz")
c2.metric("Sample rate", f"{hz_to_msps(sdr_config['sample_rate_hz']):.3f} MS/s")
c3.metric("Ganancia", f"{sdr_config['gain_db']:.1f} dB")
c4.metric("FFT", f"{sdr_config['fft_size']:,}".replace(",", "."))
c5.metric("Resolución", f"{sdr_config['frequency_resolution_hz']:.2f} Hz")

st.divider()

# ==========================================================
# RESULTADO DEL CASO
# ==========================================================
st.subheader("Resultado del caso")

d1, d2, d3, d4, d5 = st.columns(5)

estado = "SÍ" if detection["detected"] else "NO"
persistencia_actual = detection.get("persistence_hits", 0)
persistencia_requerida = detection_config["minimum_hits"]

d1.metric("Detección", estado)
d2.metric("Doppler", f"{detection['doppler_hz']:.2f} Hz")
d3.metric("SNR", f"{detection['snr_db']:.2f} dB")
d4.metric("Velocidad estimada", f"{detection['velocity_est_kmh']:.2f} km/h")
d5.metric("Persistencia", f"{persistencia_actual} / {persistencia_requerida}")

st.caption(
    f"Rango Doppler configurado: {detection_config['min_doppler_hz']:.0f}–"
    f"{detection_config['max_doppler_hz']:.0f} Hz · "
    f"Umbral: {detection_config['threshold_db']:.1f} dB"
)

if detection["detected"]:
    st.warning(
        "El sistema identificó una componente Doppler que cumplió los criterios "
        "de potencia y persistencia. En una captura sin vehículo, este resultado "
        "debe revisarse como posible falso positivo."
    )
else:
    st.success(
        "Durante la captura de referencia sin vehículo no se identificó una "
        "componente Doppler dentro del rango configurado que cumpliera los "
        "criterios de potencia y persistencia, por lo que el sistema no declaró "
        "movimiento."
    )

st.subheader("Validación manual del evento")
st.caption(
    "Confirma si el resultado automático coincide con la condición conocida del caso sin vehículo."
)

latest_event_id = len(events)
latest_timestamp = detection["timestamp"]

v1, v2 = st.columns(2)

with v1:
    if st.button("✅ Confirmar ausencia de movimiento", use_container_width=True):
        save_validation(
            latest_timestamp,
            latest_event_id,
            False,
            "confirmed_no_movement"
        )
        st.success("Ausencia de movimiento confirmada y guardada.")

with v2:
    if st.button("⚠️ Registrar falso positivo", use_container_width=True):
        save_validation(
            latest_timestamp,
            latest_event_id,
            False,
            "false_positive"
        )
        st.warning("El resultado fue registrado como falso positivo.")

gt = pd.read_csv(GROUND_TRUTH_FILE)
if not gt.empty:
    with st.expander("Ver validaciones manuales"):
        st.dataframe(gt, use_container_width=True, hide_index=True)

st.divider()

# ==========================================================
# ESPECTRO
# ==========================================================
st.subheader("Espectro actual")

fig_spectrum = go.Figure()
fig_spectrum.add_trace(
    go.Scatter(
        x=spectrum["frequency_offset_hz"],
        y=spectrum["power_db"],
        mode="lines",
        name="Espectro"
    )
)
fig_spectrum.update_layout(
    xaxis_title="Offset de frecuencia [Hz]",
    yaxis_title="Potencia [dB]",
    height=360
)
st.plotly_chart(fig_spectrum, use_container_width=True)

# ==========================================================
# WATERFALL
# ==========================================================
st.subheader("Waterfall")

waterfall_matrix = waterfall.pivot(
    index="timestamp",
    columns="frequency_offset_hz",
    values="power_db"
)

fig_waterfall = px.imshow(
    waterfall_matrix,
    aspect="auto",
    labels={
        "x": "Offset de frecuencia [Hz]",
        "y": "Tiempo",
        "color": "Potencia [dB]"
    }
)
fig_waterfall.update_layout(height=420)
st.plotly_chart(fig_waterfall, use_container_width=True)

# ==========================================================
# MÉTRICAS GENERALES
# ==========================================================
st.subheader("Indicadores de desempeño")

m1, m2, m3, m4 = st.columns(4)

m1.metric("Eventos", metrics["total_events"])
m2.metric("Tasa de detección", f"{metrics['detection_rate_percent']:.1f}%")
m3.metric("Falsos positivos", metrics["false_positives"])
m4.metric("SNR promedio", f"{metrics['average_snr_db']:.1f} dB")

st.caption(
    "La atenuación física de la portadora directa permanece pendiente de medición "
    "experimental; por ello no se presenta como indicador calculado."
)

# ==========================================================
# HISTORIAL
# ==========================================================
st.subheader("Historial de eventos")

events_display = events.copy()
events_display["timestamp"] = events_display["timestamp"].dt.strftime("%H:%M:%S")
events_display["detected"] = events_display["detected"].map({True: "Sí", False: "No"})

st.dataframe(
    events_display[
        ["timestamp", "doppler_hz", "snr_db", "velocity_est_kmh", "detected"]
    ].rename(columns={
        "timestamp": "Hora",
        "doppler_hz": "Doppler [Hz]",
        "snr_db": "SNR [dB]",
        "velocity_est_kmh": "Velocidad estimada [km/h]",
        "detected": "Detectado"
    }),
    use_container_width=True,
    hide_index=True
)

# ==========================================================
# INFORMACIÓN TÉCNICA
# ==========================================================
with st.expander("Ver configuración técnica completa"):
    st.json(sdr_config)
