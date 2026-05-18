import streamlit as st
import pandas as pd
import io
from fpdf import FPDF

from utils import (
    aplicar_estilo, header, verificar_login,
    cargar_tickets, guardar_tickets
)

st.set_page_config(page_title="Tickets", layout="wide")
aplicar_estilo()
verificar_login()

# Solo rol ventas puede editar tickets
if st.session_state.rol != "ventas":
    st.error("Acceso restringido. Esta seccion es solo para el area de ventas.")
    st.stop()

header("Tickets de Cotizacion", "Revisa, edita y aprueba los tickets generados por los coordinadores.")

# ------------------------------------------------------------------
# Cargar tickets
# ------------------------------------------------------------------
tickets_df = cargar_tickets()

if tickets_df.empty:
    st.info("No hay tickets registrados aun.")
    st.stop()

# ------------------------------------------------------------------
# Filtros
# ------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    estatus_opciones = ["Todos"] + sorted(tickets_df["estatus"].unique().tolist())
    filtro_estatus   = st.selectbox("Filtrar por estatus", estatus_opciones)

with col2:
    cliente_opciones = ["Todos"] + sorted(tickets_df["cliente"].unique().tolist())
    filtro_cliente   = st.selectbox("Filtrar por cliente", cliente_opciones)

with col3:
    fechas = sorted(tickets_df["fecha"].unique().tolist(), reverse=True)
    fecha_opciones = ["Todas"] + fechas
    filtro_fecha   = st.selectbox("Filtrar por fecha", fecha_opciones)

# Aplicar filtros
df_filtrado = tickets_df.copy()
if filtro_estatus != "Todos":
    df_filtrado = df_filtrado[df_filtrado["estatus"] == filtro_estatus]
if filtro_cliente != "Todos":
    df_filtrado = df_filtrado[df_filtrado["cliente"] == filtro_cliente]
if filtro_fecha != "Todas":
    df_filtrado = df_filtrado[df_filtrado["fecha"] == filtro_fecha]

st.markdown(f"**{len(df_filtrado)} ticket(s) encontrados**")

# ------------------------------------------------------------------
# Tabla con vista de tickets filtrados
# ------------------------------------------------------------------
columnas_vista = [
    "folio", "fecha", "usuario", "cliente",
    "origen_estado", "destino_estado", "tipo_equipo",
    "costo_estimado", "costo_final", "estatus"
]

st.dataframe(
    df_filtrado[columnas_vista].reset_index(drop=True),
    use_container_width=True
)

# ------------------------------------------------------------------
# Descargar tabla filtrada a Excel
# ------------------------------------------------------------------
def df_a_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tickets")
    return buffer.getvalue()

st.download_button(
    label="Descargar tabla en Excel",
    data=df_a_excel(df_filtrado[columnas_vista]),
    file_name="tickets_fli.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.markdown("---")

# ------------------------------------------------------------------
# Edicion de ticket individual
# ------------------------------------------------------------------
st.markdown("#### Editar ticket")

folio_seleccionado = st.selectbox(
    "Selecciona un folio para editar",
    df_filtrado["folio"].tolist()
)

if folio_seleccionado:
    idx    = tickets_df[tickets_df["folio"] == folio_seleccionado].index[0]
    ticket = tickets_df.loc[idx]

    st.markdown(f"""
        <div class="fli-card">
            <h3>Ticket {ticket['folio']}</h3>
            <p><b>Fecha:</b> {ticket['fecha']} &nbsp;|&nbsp;
               <b>Generado por:</b> {ticket['usuario']}</p>
            <p><b>Cliente:</b> {ticket['cliente']}</p>
            <p><b>Ruta:</b> {ticket['origen_estado']} &rarr; {ticket['destino_estado']}</p>
            <p><b>Equipo:</b> {ticket['tipo_equipo']} &nbsp;|&nbsp;
               <b>Flujo:</b> {ticket['flujo']} &nbsp;|&nbsp;
               <b>Rango:</b> {ticket['rango']}</p>
            <p><b>Costo estimado:</b> ${ticket['costo_estimado']:,.2f} MXN</p>
        </div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        costo_final_nuevo = st.number_input(
            "Costo final (MXN)",
            min_value=0.0,
            value=float(ticket["costo_final"]),
            step=500.0,
            format="%.2f"
        )

    with col_b:
        estatus_nuevo = st.selectbox(
            "Estatus",
            ["Pendiente", "Aprobado", "Rechazado"],
            index=["Pendiente", "Aprobado", "Rechazado"].index(ticket["estatus"])
            if ticket["estatus"] in ["Pendiente", "Aprobado", "Rechazado"] else 0
        )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("Guardar cambios"):
            tickets_df.at[idx, "costo_final"] = costo_final_nuevo
            tickets_df.at[idx, "estatus"]      = estatus_nuevo
            guardar_tickets(tickets_df)
            st.success("Cambios guardados correctamente.")
            import time
            time.sleep(1.5)
            st.rerun()

    with col_btn2:
        # Descargar PDF del ticket individual
        def generar_pdf_ticket(t) -> bytes:
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
                ("Folio",             t["folio"]),
                ("Fecha",             t["fecha"]),
                ("Generado por",      t["usuario"]),
                ("Cliente",           t["cliente"]),
                ("Estado de origen",  t["origen_estado"]),
                ("Estado de destino", t["destino_estado"]),
                ("Tipo de equipo",    t["tipo_equipo"]),
                ("Flujo",             t["flujo"]),
                ("Rango",             t["rango"]),
                ("Costo estimado",    f"${float(t['costo_estimado']):,.2f} MXN"),
                ("Costo final",       f"${float(t['costo_final']):,.2f} MXN"),
                ("Estatus",           t["estatus"]),
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

        st.download_button(
            label="Descargar ticket PDF",
            data=generar_pdf_ticket(ticket),
            file_name=f"ticket_{folio_seleccionado}.pdf",
            mime="application/pdf"
        )
