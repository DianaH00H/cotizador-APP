import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from fpdf import FPDF
import io

from utils import (
    aplicar_estilo, header, verificar_login,
    cargar_modelo, cargar_tickets, guardar_tickets, siguiente_folio
)

st.set_page_config(page_title="Nueva Cotizacion", layout="wide")
aplicar_estilo()
verificar_login()

# Solo rol carrier puede cotizar
if st.session_state.rol != "carrier":
    st.error("Acceso restringido. Esta seccion es solo para coordinadores de transportistas.")
    st.stop()

header("Nueva Cotizacion", "Ingresa los datos del flete para generar una estimacion de costo.")

# ------------------------------------------------------------------
# Cargar modelo y encoders
# ------------------------------------------------------------------
@st.cache_resource
def get_modelo():
    return cargar_modelo()

payload  = get_modelo()
modelo   = payload["modelo"]
encoders = payload["encoders"]
mae      = payload["metricas"]["mae"]

# ------------------------------------------------------------------
# Opciones de cada dropdown — se extraen de los encoders entrenados
# ------------------------------------------------------------------
def opciones(col: str) -> list:
    return sorted(encoders[col].classes_.tolist())


# ------------------------------------------------------------------
# Formulario de cotizacion
# ------------------------------------------------------------------
with st.form("form_cotizacion"):
    col1, col2 = st.columns(2)

    with col1:
        cliente      = st.selectbox("Cliente",        opciones("CLIENTE"))
        origen_est   = st.selectbox("Estado de origen",  opciones("ORIGEN_ESTADO"))
        destino_est  = st.selectbox("Estado de destino", opciones("DESTINO_ESTADO"))

    with col2:
        tipo_equipo  = st.selectbox("Tipo de equipo", opciones("TIPO_DE_EQUIPO"))
        flujo        = st.selectbox("Flujo",          opciones("FLUJO"))
        rango        = st.selectbox("Rango",          opciones("RANGO"))

    cotizar = st.form_submit_button("Cotizar")


# ------------------------------------------------------------------
# Prediccion
# ------------------------------------------------------------------
if cotizar:
    def encode(col, valor):
        le = encoders[col]
        if valor in le.classes_:
            return int(le.transform([valor])[0])
        # Si el valor no estaba en entrenamiento usar 'Desconocido'
        return int(le.transform(["Desconocido"])[0])

    X_nuevo = pd.DataFrame([{
        "TIPO_DE_EQUIPO": encode("TIPO_DE_EQUIPO", tipo_equipo),
        "CLIENTE":        encode("CLIENTE",        cliente),
        "FLUJO":          encode("FLUJO",          flujo),
        "RANGO":          encode("RANGO",          rango),
        "COSTO_EN_MXN":   0,       # placeholder, se elimina antes de predecir
        "ORIGEN_ESTADO":  encode("ORIGEN_ESTADO",  origen_est),
        "DESTINO_ESTADO": encode("DESTINO_ESTADO", destino_est),
    }])

    features = payload["features"]
    X_nuevo  = X_nuevo[features]

    costo_estimado = float(modelo.predict(X_nuevo)[0])
    rango_min      = max(0, costo_estimado - mae)
    rango_max      = costo_estimado + mae

    st.session_state["ultima_cotizacion"] = {
        "cliente":      cliente,
        "origen":       origen_est,
        "destino":      destino_est,
        "tipo_equipo":  tipo_equipo,
        "flujo":        flujo,
        "rango":        rango,
        "costo_estimado": round(costo_estimado, 2),
        "rango_min":    round(rango_min, 2),
        "rango_max":    round(rango_max, 2),
    }


# ------------------------------------------------------------------
# Mostrar resultado y ticket
# ------------------------------------------------------------------
if "ultima_cotizacion" in st.session_state:
    c = st.session_state["ultima_cotizacion"]

    st.markdown(f"""
        <div class="fli-card">
            <h3>Resultado de la cotizacion</h3>
            <p><b>Cliente:</b> {c['cliente']}</p>
            <p><b>Ruta:</b> {c['origen']} &rarr; {c['destino']}</p>
            <p><b>Equipo:</b> {c['tipo_equipo']} &nbsp;|&nbsp;
               <b>Flujo:</b> {c['flujo']} &nbsp;|&nbsp;
               <b>Rango:</b> {c['rango']}</p>
            <hr style="border-color:#0A2342; margin: 0.8rem 0;">
            <p style="font-size:1.3rem;">
                <b>Costo estimado:</b>
                ${c['rango_min']:,.0f} &mdash; ${c['rango_max']:,.0f} MXN
            </p>
            <p style="color:#555; font-size:0.85rem;">
                Punto medio: ${c['costo_estimado']:,.0f} MXN
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Guardar ticket")

    tickets_df = cargar_tickets()
    folio      = siguiente_folio(tickets_df)
    fecha_hoy  = date.today().strftime("%Y-%m-%d")

    st.write(f"Folio asignado: **{folio}**  |  Fecha: **{fecha_hoy}**")

    if st.button("Guardar ticket"):
        nuevo = {
            "folio":          folio,
            "fecha":          fecha_hoy,
            "usuario":        st.session_state.usuario,
            "cliente":        c["cliente"],
            "origen_estado":  c["origen"],
            "destino_estado": c["destino"],
            "tipo_equipo":    c["tipo_equipo"],
            "flujo":          c["flujo"],
            "rango":          c["rango"],
            "costo_estimado": c["costo_estimado"],
            "costo_final":    c["costo_estimado"],
            "estatus":        "Pendiente",
        }
        tickets_df = pd.concat(
            [tickets_df, pd.DataFrame([nuevo])], ignore_index=True
        )
        guardar_tickets(tickets_df)
        st.success(f"Ticket {folio} guardado correctamente.")

        # Generar PDF del ticket
        def generar_pdf(datos: dict) -> bytes:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_fill_color(10, 35, 66)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 12, "FLI Cotizador - Ticket de Cotizacion", ln=True, fill=True)

            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(10, 35, 66)
            pdf.ln(6)

            campos = [
                ("Folio",            datos["folio"]),
                ("Fecha",            datos["fecha"]),
                ("Generado por",     datos["usuario"]),
                ("Cliente",          datos["cliente"]),
                ("Estado de origen", datos["origen_estado"]),
                ("Estado de destino",datos["destino_estado"]),
                ("Tipo de equipo",   datos["tipo_equipo"]),
                ("Flujo",            datos["flujo"]),
                ("Rango",            datos["rango"]),
                ("Costo estimado",   f"${datos['costo_estimado']:,.2f} MXN"),
                ("Rango de precio",  f"${datos['rango_min']:,.0f} - ${datos['rango_max']:,.0f} MXN"),
                ("Estatus",          "Pendiente"),
            ]

            for label, valor in campos:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(55, 9, f"{label}:", ln=False)
                pdf.set_font("Helvetica", "", 11)
                pdf.cell(0, 9, str(valor), ln=True)

            pdf.ln(4)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 8, "Este documento es una estimacion generada automaticamente.", ln=True)
            pdf.cell(0, 8, "El precio final puede ser ajustado por el area de ventas.", ln=True)

            return bytes(pdf.output())

        pdf_bytes = generar_pdf({
            "folio":          folio,
            "fecha":          fecha_hoy,
            "usuario":        st.session_state.usuario,
            "cliente":        c["cliente"],
            "origen_estado":  c["origen"],
            "destino_estado": c["destino"],
            "tipo_equipo":    c["tipo_equipo"],
            "flujo":          c["flujo"],
            "rango":          c["rango"],
            "costo_estimado": c["costo_estimado"],
            "rango_min":      c["rango_min"],
            "rango_max":      c["rango_max"],
        })

        st.download_button(
            label="Descargar ticket PDF",
            data=pdf_bytes,
            file_name=f"ticket_{folio}.pdf",
            mime="application/pdf"
        )

        del st.session_state["ultima_cotizacion"]
