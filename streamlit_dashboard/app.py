
from pathlib import Path
import json
import subprocess
import sys
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

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from radar_app.captures import CaptureRepository
from radar_app.orchestrator import CaptureOrchestrator
from radar_app.processing import ensure_detection_config
from radar_app.validation import record_validation, summarize_repository

CAPTURE_REPOSITORY = CaptureRepository(BASE_DIR / "captures")
ORCHESTRATOR = CaptureOrchestrator(CAPTURE_REPOSITORY)

@st.cache_data(ttl=60)
def gnu_radio_environment():
    return ORCHESTRATOR.check_gnu_radio_environment()

try:
    AVAILABLE_CAPTURES = CAPTURE_REPOSITORY.discover()
except (OSError, ValueError, json.JSONDecodeError) as error:
    st.error(f"No se pudo construir el catálogo de capturas: {error}")
    st.stop()

if not AVAILABLE_CAPTURES:
    st.info("Todavía no existen capturas. Cree una para comenzar.")
    st.stop()

with st.sidebar.expander("Nueva captura", expanded=False):
    with st.form("new_capture_form", clear_on_submit=True):
        new_capture_name = st.text_input("Nombre")
        new_capture_kind_label = st.selectbox(
            "Tipo de ensayo",
            options=["Objeto o persona", "Vehículo", "Referencia sin movimiento"],
        )
        new_capture_notes = st.text_area("Notas", height=80)
        create_capture = st.form_submit_button("Crear captura", use_container_width=True)

    if create_capture:
        kind_by_label = {
            "Objeto o persona": "human",
            "Vehículo": "vehicle",
            "Referencia sin movimiento": "baseline",
        }
        try:
            created_capture = CAPTURE_REPOSITORY.create(
                new_capture_name,
                kind=kind_by_label[new_capture_kind_label],
                notes=new_capture_notes,
            )
        except (OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.success(f"Captura creada: {created_capture.display_name}")
            st.rerun()

CAPTURES_BY_ID = {capture.capture_id: capture for capture in AVAILABLE_CAPTURES}

selected_capture_id = st.sidebar.selectbox(
    "Seleccione el caso experimental",
    options=list(CAPTURES_BY_ID),
    format_func=lambda capture_id: CAPTURES_BY_ID[capture_id].display_name,
)
SELECTED_CAPTURE = CAPTURES_BY_ID[selected_capture_id]
CASE_NAME = SELECTED_CAPTURE.display_name.upper()
CASE_DIR = SELECTED_CAPTURE.root
IS_HUMAN_CASE = SELECTED_CAPTURE.kind == "human"
IS_VEHICLE_CASE = SELECTED_CAPTURE.kind == "vehicle"
IS_MOVEMENT_CASE = IS_HUMAN_CASE or IS_VEHICLE_CASE
CONFIG_DIR = SELECTED_CAPTURE.config_dir
REALTIME_DIR = SELECTED_CAPTURE.raw_dir
PROCESSED_DIR = SELECTED_CAPTURE.processed_dir
CONFIG_FILE = CONFIG_DIR / "sdr_config.json"
DETECTION_CONFIG_FILE = CONFIG_DIR / "detection_config.json"
SPECTRUM_FILE = REALTIME_DIR / "spectrum_latest.csv"
WATERFALL_FILE = REALTIME_DIR / "waterfall.csv"
EVENTS_FILE = PROCESSED_DIR / "events.csv"
METRICS_FILE = PROCESSED_DIR / "metrics.json"
DETECTION_FILE = PROCESSED_DIR / "detection_latest.json"
GROUND_TRUTH_FILE = PROCESSED_DIR / "ground_truth.csv"

show_global_summary = st.sidebar.checkbox("Ver resumen global de validación")
if show_global_summary:
    summary = summarize_repository(CAPTURE_REPOSITORY)
    overall = summary["overall"]
    st.title("Resumen global de validación")
    st.caption("Solo incluye capturas con observación manual bajo el contrato actual.")

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Ensayos validados", overall["total"])
    g2.metric(
        "Exactitud",
        "N/D" if overall["accuracy_percent"] is None else f"{overall['accuracy_percent']:.1f}%",
    )
    g3.metric(
        "Tasa de detección",
        "N/D" if overall["detection_rate_percent"] is None else f"{overall['detection_rate_percent']:.1f}%",
    )
    g4.metric(
        "Tasa de falsos positivos",
        "N/D" if overall["false_positive_rate_percent"] is None else f"{overall['false_positive_rate_percent']:.1f}%",
    )
    st.caption(f"Capturas todavía no validadas: {summary['unvalidated_captures']}")

    if overall["total"]:
        confusion = [[overall["TN"], overall["FP"]], [overall["FN"], overall["TP"]]]
        fig_confusion = px.imshow(
            confusion,
            x=["Predicción: reposo", "Predicción: movimiento"],
            y=["Observado: reposo", "Observado: movimiento"],
            text_auto=True,
            color_continuous_scale="Blues",
            labels={"color": "Ensayos"},
        )
        fig_confusion.update_layout(title="Matriz de confusión", height=420)
        st.plotly_chart(fig_confusion, use_container_width=True)

        st.subheader("Resultados por perfil")
        kind_names = {
            "human": "Objeto o persona",
            "vehicle": "Vehículo",
            "baseline": "Referencia sin movimiento",
            "unknown": "Sin clasificar",
        }
        profile_rows = []
        for kind, values in summary["by_kind"].items():
            profile_rows.append({
                "Perfil": kind_names[kind],
                "Ensayos": values["total"],
                "TP": values["TP"],
                "TN": values["TN"],
                "FP": values["FP"],
                "FN": values["FN"],
                "Exactitud [%]": values["accuracy_percent"],
            })
        st.dataframe(pd.DataFrame(profile_rows), use_container_width=True, hide_index=True)

        st.subheader("Ensayos validados")
        trial_rows = pd.DataFrame(summary["trials"])
        trial_rows["predicted_movement"] = trial_rows["predicted_movement"].map({True: "Movimiento", False: "Reposo"})
        trial_rows["observed_movement"] = trial_rows["observed_movement"].map({True: "Movimiento", False: "Reposo"})
        st.dataframe(
            trial_rows.rename(columns={
                "name": "Captura",
                "kind": "Perfil",
                "predicted_movement": "Predicción",
                "observed_movement": "Observado",
                "outcome": "Resultado",
                "validated_at": "Validada",
                "notes": "Notas",
            })[["Captura", "Perfil", "Predicción", "Observado", "Resultado", "Validada", "Notas"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Valide al menos una captura para construir las métricas globales.")
    st.stop()

if SELECTED_CAPTURE.metadata["status"] != "completed":
    st.title("📡 Radar Doppler Pasivo Monocanal")
    st.info(f"Captura preparada: **{SELECTED_CAPTURE.display_name}**")
    st.caption(
        f"ID: `{SELECTED_CAPTURE.capture_id}` · "
        f"Estado: {SELECTED_CAPTURE.metadata['status']}"
    )
    current_status = SELECTED_CAPTURE.metadata["status"]
    if current_status == "captured":
        st.success("La adquisición real terminó y los datos originales están guardados.")
        if st.button("Procesar datos guardados", type="primary", use_container_width=True):
            with st.spinner("Analizando la actividad Doppler..."):
                try:
                    ORCHESTRATOR.process_existing_capture(SELECTED_CAPTURE.capture_id)
                except (OSError, RuntimeError, ValueError) as error:
                    st.error(f"El procesamiento falló: {error}")
                else:
                    st.success("Procesamiento completado.")
                    st.rerun()
        st.stop()

    if current_status == "failed" and SELECTED_CAPTURE.metadata.get("error"):
        st.error(SELECTED_CAPTURE.metadata["error"])

    st.write("La captura ya tiene sus carpetas de configuración, datos originales y resultados.")
    pending_detection_config = ensure_detection_config(SELECTED_CAPTURE)
    baseline_seconds = int(pending_detection_config.get("baseline_instants", 5))
    minimum_duration = baseline_seconds + 5
    default_duration = max(25 if IS_MOVEMENT_CASE else 15, minimum_duration)
    st.info(
        f"Protocolo: {baseline_seconds} s iniciales de reposo y "
        f"{default_duration - baseline_seconds} s de evaluación con la duración predeterminada."
    )
    capture_duration = st.number_input(
        "Duración de la captura real [s]",
        min_value=minimum_duration,
        max_value=300,
        value=default_duration,
        step=5,
    )
    action_left, action_center, action_right = st.columns(3)
    with action_left:
        if st.button("Ejecutar simulación", type="secondary", use_container_width=True):
            with st.spinner("Capturando y procesando datos simulados..."):
                try:
                    ORCHESTRATOR.simulate(SELECTED_CAPTURE.capture_id)
                except (OSError, ValueError) as error:
                    st.error(f"La simulación falló: {error}")
                else:
                    st.success("Captura simulada completada.")
                    st.rerun()
    gnu_environment = gnu_radio_environment()
    with action_center:
        start_hardware = st.button(
            "Iniciar con RTL-SDR",
            type="primary",
            disabled=not gnu_environment["ready"],
            use_container_width=True,
        )
    with action_right:
        st.write("Mantenga despejada la zona observada durante el período inicial de referencia.")
    if start_hardware:
        with st.spinner("GNU Radio está capturando. No desconecte el RTL-SDR..."):
            try:
                ORCHESTRATOR.run_hardware_capture(
                    SELECTED_CAPTURE.capture_id,
                    float(capture_duration),
                )
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                st.error(f"La captura real falló: {error}")
            else:
                st.success("Adquisición real y procesamiento completados.")
                st.rerun()
    if gnu_environment["ready"]:
        st.success(f"GNU Radio preparado: `{gnu_environment['python']}`")
        st.caption("El entorno está listo para iniciar una adquisición con el RTL-SDR conectado.")
    else:
        st.warning(f"GNU Radio no disponible: {gnu_environment.get('error', 'error desconocido')}")
    st.stop()

# ==========================================================
# FUNCIONES DE LECTURA
# ==========================================================
def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def read_csv(path):
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        if path == EVENTS_FILE:
            return pd.DataFrame(columns=["timestamp", "detected"])
        raise

def hz_to_mhz(value):
    return value / 1_000_000

def hz_to_msps(value):
    return value / 1_000_000

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
except Exception as e:
    st.error(f"No se pudieron cargar los archivos de entrada: {e}")
    st.stop()

# Normalización básica
if "detected" not in events.columns:
    events["detected"] = None
if "timestamp" not in events.columns:
    events["timestamp"] = events.get("event_start", pd.Series(index=events.index, dtype="object"))
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
st.caption(
    f"ID: `{SELECTED_CAPTURE.capture_id}` · "
    f"Estado: {SELECTED_CAPTURE.metadata['status']} · "
    f"Creada: {SELECTED_CAPTURE.metadata['created_at']}"
)

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

estado = "SÍ" if detection["detected"] else "NO"

if IS_VEHICLE_CASE:
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Movimiento detectado", estado)
    d2.metric("Doppler representativo", f"{detection['doppler_hz']:.3f} Hz")
    d3.metric("Exceso sobre reposo", f"{detection['excess_db']:.2f} dB")
    speed = detection.get("velocity_est_kmh")
    d4.metric("Velocidad estimada", "No calibrada" if speed is None else f"{speed:.2f} km/h")
    e1, e2, e3, e4 = st.columns(4)
    known_speed = detection.get("known_speed_kmh")
    e1.metric("Velocidad de referencia", "No definida" if known_speed is None else f"≈ {known_speed:.0f} km/h")
    e2.metric("Bins activos", detection['active_bins'])
    e3.metric("Persistencia / mínimo", f"{detection['persistence_hits']} / {detection['minimum_hits']}")
    e4.metric("Eventos detectados", metrics['total_events'])
    st.caption(
        f"Banda Doppler: {detection['doppler_band_min_hz']:.1f}–{detection['doppler_band_max_hz']:.1f} Hz · "
        f"Umbral: {detection['threshold_db']:.1f} dB · Mínimo de bins: {detection['minimum_active_bins']}"
    )
    if detection['detected']:
        st.success("El procesamiento identificó un evento Doppler compatible con vehículo que cumple los criterios configurados.")
    else:
        st.info("El procesamiento no declaró movimiento en este resultado.")
    st.warning("La estimación de velocidad vehicular permanece sin calibrar para la geometría biestática.")
    if detection.get('ground_truth_timing') == 'PENDIENTE_CONFIRMACION_TEMPORAL':
        st.warning("Está pendiente confirmar temporalmente que el evento detectado coincide con el paso del vehículo. Las tasas de desempeño aún no deben interpretarse como validadas.")
    st.caption(f"Intervalo del evento: {detection.get('event_start', 'N/D')} → {detection.get('event_end', 'N/D')}")
elif IS_HUMAN_CASE:
    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("Movimiento detectado", estado)
    d2.metric("Doppler representativo", f"{detection['doppler_hz']:.3f} Hz")
    d3.metric("Exceso sobre reposo", f"{detection['excess_db']:.3f} dB")
    d4.metric("Bins activos", detection["active_bins"])
    d5.metric("Eventos válidos", metrics["total_events"])
    d6.metric("Velocidad equivalente*", f"{detection['velocity_est_kmh']:.2f} km/h")

    st.caption(
        f"Banda Doppler humana: {detection_config['min_doppler_hz']:.1f}–"
        f"{detection_config['max_doppler_hz']:.1f} Hz · "
        f"Mínimo de bins activos: {detection_config['minimum_active_bins']} · "
        f"Persistencia: {detection.get('persistence_hits', 0)} / "
        f"{detection_config['minimum_hits']}"
    )
    (st.success if detection["detected"] else st.info)(
        ("El sistema no declaró movimiento en esta captura." if not detection["detected"] else
        "En la captura con persona se identificó actividad Doppler de baja "
        "frecuencia que superó el nivel de reposo y cumplió los criterios de "
        "bins activos y persistencia, por lo que el sistema declaró movimiento.")
    )
    st.warning(
        "* La velocidad indicada es una velocidad equivalente obtenida mediante "
        "un modelo Doppler simplificado; no corresponde a la velocidad real de caminata."
    )
else:
    d1, d2, d3, d4, d5 = st.columns(5)
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
    (st.warning if detection["detected"] else st.success)(
        ("El sistema declaró movimiento en el escenario sin vehículo; revise si corresponde a un falso positivo." if detection["detected"] else
        "Durante la captura de referencia sin vehículo no se identificó una "
        "componente Doppler dentro del rango configurado que cumpliera los "
        "criterios de potencia y persistencia, por lo que el sistema no declaró "
        "movimiento.")
    )

st.subheader("Validación manual del evento")
st.caption(
    "Registra lo que realmente se observó durante el ensayo, independientemente de la predicción."
)

validation_notes = st.text_input("Notas de validación (opcional)")
v1, v2 = st.columns(2)

with v1:
    if st.button("Se observó movimiento", use_container_width=True):
        try:
            record_validation(SELECTED_CAPTURE, True, validation_notes)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            st.error(f"No se pudo guardar la validación: {error}")
        else:
            st.success("Observación guardada y métricas actualizadas.")
            st.rerun()

with v2:
    if st.button("No se observó movimiento", use_container_width=True):
        try:
            record_validation(SELECTED_CAPTURE, False, validation_notes)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            st.error(f"No se pudo guardar la validación: {error}")
        else:
            st.success("Observación guardada y métricas actualizadas.")
            st.rerun()

outcome_names = {
    "TP": "Acierto: movimiento detectado y observado",
    "TN": "Acierto: ausencia detectada y observada",
    "FP": "Falso positivo",
    "FN": "Falso negativo",
}
if detection.get("validation_outcome"):
    st.info(f"Última validación: **{outcome_names[detection['validation_outcome']]}**")

gt = pd.read_csv(GROUND_TRUTH_FILE) if GROUND_TRUTH_FILE.exists() else pd.DataFrame()
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

if IS_VEHICLE_CASE:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eventos detectados", metrics['total_events'])
    m2.metric("Máximo Doppler", f"{metrics['max_doppler_hz']:.3f} Hz")
    m3.metric("Instantes analizados", metrics['total_instants'])
    m4.metric("Instantes de referencia", metrics['baseline_instants'])
elif IS_HUMAN_CASE:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eventos detectados", metrics["total_events"])
    m2.metric("Exceso promedio sobre reposo", f"{metrics['average_snr_db']:.3f} dB")
    m3.metric("Máximo Doppler", f"{metrics['max_doppler_hz']:.3f} Hz")
    m4.metric("Instantes analizados", metrics["total_instants"])
else:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eventos", metrics["total_events"])
    detection_rate = metrics.get("detection_rate_percent")
    m2.metric("Tasa de detección", "N/D" if detection_rate is None else f"{detection_rate:.1f}%")
    m3.metric("Falsos positivos", metrics.get("false_positives", "N/D") if metrics.get("false_positives") is not None else "N/D")
    m4.metric("SNR promedio", f"{metrics['average_snr_db']:.1f} dB")

if metrics.get("validated_trials", 0):
    st.markdown("#### Validación observacional")
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("Ensayos validados", metrics["validated_trials"])
    accuracy = metrics.get("accuracy_percent")
    q2.metric("Exactitud", "N/D" if accuracy is None else f"{accuracy:.1f}%")
    q3.metric("Aciertos con movimiento", metrics.get("true_positives", 0))
    q4.metric("Falsos positivos", metrics.get("false_positives", 0))
    q5.metric("Falsos negativos", metrics.get("false_negatives", 0))

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

if IS_VEHICLE_CASE:
    history_columns = ["timestamp", "event_start", "event_end", "doppler_hz", "excess_db", "active_bins", "event_hits", "persistence_hits", "detected"]
    history_names = {
        "timestamp": "Hora", "event_start": "Inicio", "event_end": "Fin",
        "doppler_hz": "Doppler representativo [Hz]", "excess_db": "Exceso sobre reposo [dB]",
        "active_bins": "Bins activos", "event_hits": "Persistencia", "persistence_hits": "Persistencia",
        "detected": "Detectado",
    }
elif IS_HUMAN_CASE:
    history_columns = [
        "timestamp", "doppler_hz", "excess_db", "active_bins",
        "event_hits", "velocity_est_kmh", "detected"
    ]
    history_names = {
        "timestamp": "Hora",
        "doppler_hz": "Doppler representativo [Hz]",
        "excess_db": "Exceso sobre reposo [dB]",
        "active_bins": "Bins activos",
        "event_hits": "Eventos válidos",
        "velocity_est_kmh": "Velocidad equivalente [km/h]",
        "detected": "Detectado",
    }
else:
    history_columns = [
        "timestamp", "doppler_hz", "snr_db", "velocity_est_kmh", "detected"
    ]
    history_names = {
        "timestamp": "Hora",
        "doppler_hz": "Doppler [Hz]",
        "snr_db": "SNR [dB]",
        "velocity_est_kmh": "Velocidad estimada [km/h]",
        "detected": "Detectado",
    }

st.dataframe(
    events_display[[c for c in history_columns if c in events_display.columns]].rename(columns=history_names),
    use_container_width=True,
    hide_index=True,
)

# ==========================================================
# INFORMACIÓN TÉCNICA
# ==========================================================
with st.expander("Ver configuración técnica completa"):
    st.markdown("**Configuración SDR**")
    st.json(sdr_config)
    st.markdown("**Configuración de detección**")
    st.json(detection_config)
