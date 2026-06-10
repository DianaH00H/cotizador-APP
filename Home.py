import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
from fpdf import FPDF
import pickle
from pathlib import Path
import io
import sys

from utils import (
    aplicar_estilo, USUARIOS,
    cargar_modelo, cargar_tickets, guardar_tickets, siguiente_folio
)

st.set_page_config(
    page_title="FLI Cotizador",
    page_icon=None,
    layout="wide"
)

aplicar_estilo()

if "usuario" not in ss: ss.usuario = None
if "rol"     not in ss: ss.rol     = None



def login_page():
    st.markdown("""
        <style>
            [data-testid="stSidebar"]        { display: none; }
            [data-testid="collapsedControl"] { display: none; }

            .stApp { background-color: #6b5b95 !important; }
            .block-container { padding-top: 8rem !important; }

            /* Target the actual column container */
            div[data-testid="column"] {
                background-color: #EBBA07 !important;
                border-radius: 24px !important;
                padding: 2rem !important;
            }

            /* Make the form background transparent */
            div[data-testid="stForm"] {
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
            }

            /* White inputs */
            input {
                background-color: #FFFFFF !important;
                border-radius: 8px !important;
                border: none !important;
                color: #333 !important;
                padding: 0.5rem 1rem !important;
            }

            /* White labels */
            label p {
                color: #FFFFFF !important;
                font-weight: 500 !important;
            }

            /* Button styling */
            button[kind="primaryFormSubmit"] {
                background-color: #EBBA07 !important;
                color: #EBBA07 !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 0.5rem !important;
            }

            button[kind="primaryFormSubmit"]:hover {
                background-color: #EBBA07 !important;
            }

            /* Alert styling with transparency */
            div[data-testid="stNotification"],
            .stAlert {
                background-color: rgba(74, 65, 112, 0.8) !important;  /* 0.8 = 80% opacity */
                border: none !important;
            }
            .stAlert p,
            .stAlert div,
            div[data-testid="stNotification"] p {
                color: #C4BFDB !important;
            }
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([2, 1.2, 2])

    with col:
        st.markdown("""
            <h1 style="color:#FFFFFF; text-align:center;
                       font-size:2rem; margin:0 0 0.3rem 0;">
                FLI Cotizador
            </h1>
            <p style="color:#e0d7f5; text-align:center;
                      font-size:0.9rem; margin:0 0 1.5rem 0;">
                Sistema de cotizacion de fletes
            </p>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            usuario    = st.text_input("Usuario")
            contrasena = st.text_input("Contraseña", type="password")
            entrar     = st.form_submit_button("Entrar", use_container_width=True)

    if entrar:
        if usuario in USUARIOS and USUARIOS[usuario]["password"] == contrasena:
            ss.usuario = usuario
            ss.rol     = USUARIOS[usuario]["rol"]
            if ss.rol == "carrier":
                ss.runpage = cotizacion_page
            elif ss.rol == "ventas":
                ss.runpage = tickets_page
            elif ss.rol == "modelado":
                ss.runpage = modelado_page
            else:
                ss.runpage = cobranza_page
            st.rerun()
        else:
            st.error("Usuario o contrasena incorrectos.")

def _header_with_logout(titulo: str, subtitulo: str = ""):
    st.markdown("""
        <style>
            [data-testid="stSidebar"]        { display: none; }
            [data-testid="collapsedControl"] { display: none; }

            .cerrar-btn button {
                background-color: white !important;
                font-weight: bold !important;
                border: 2px solid #6b5b95 !important;
                color: #6b5b95 !important;
                width: 100% !important;
            }
            .cerrar-btn button:hover {
                background-color: #6b5b95 !important;
                color: white !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
        <div style="background-color:#6b5b95; padding: 2rem 2.5rem;
                    border-radius: 10px; margin-bottom: 0.5rem;">
            <h1 style="color:#FFFFFF; margin:0; font-size:2.2rem;">
                FLI Cotizador &nbsp;|&nbsp; {titulo}
            </h1>
            <p style="color:#e0d7f5; margin:0.3rem 0 0 0; font-size:1rem;">
                {subtitulo}
            </p>
        </div>
    """, unsafe_allow_html=True)

    _, col_btn = st.columns([5, 1])
    with col_btn:
        st.markdown('<div class="cerrar-btn">', unsafe_allow_html=True)
        if st.button("Cerrar sesión", use_container_width=True):
            ss.usuario = None
            ss.rol     = None
            ss.runpage = login_page
            if "ultima_cotizacion" in ss:
                del ss["ultima_cotizacion"]
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def cotizacion_page():
    _header_with_logout("Nueva Cotizacion", "Ingresa los datos del flete para generar una estimacion de costo.")

    if "modelo_payload" not in ss:
        ss.modelo_payload = cargar_modelo()

    payload  = ss.modelo_payload
    modelo   = payload["modelo"]
    encoders = payload["encoders"]
    mae      = payload["metricas"]["mae"]

    def opciones(col):
        return sorted(encoders[col].classes_.tolist())

    def encode(col, valor):
        le = encoders[col]
        if valor in le.classes_:
            return int(le.transform([valor])[0])
        return int(le.transform(["Desconocido"])[0])

    with st.form("form_cotizacion"):

        # --- Tarjeta 1: Datos del flete ---
        st.markdown("""
            <div style="background-color:#f5f3fa; border-left: 4px solid #6b5b95;
                        padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 1rem;">
                <h4 style="color:#6b5b95; margin:0 0 0.8rem 0;">Datos del flete</h4>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            cliente    = st.selectbox("Cliente",           opciones("CLIENTE"))
        with col2:
            origen_est = st.selectbox("Estado de origen",  opciones("ORIGEN_ESTADO"))
        with col3:
            destino_est = st.selectbox("Estado de destino", opciones("DESTINO_ESTADO"))

        col4, col5 = st.columns(2)
        with col4:
            flujo = st.selectbox("Flujo", opciones("FLUJO"))
        with col5:
            rango = st.selectbox("Rango", opciones("RANGO"))

        st.markdown("</div>", unsafe_allow_html=True)

        # --- Tarjeta 2: Características del flete (desplegable) ---
        with st.expander("Características del flete  —  opcional"):
            st.markdown("""
                <p style="color:#888; font-size:0.85rem; margin-bottom:0.8rem;">
                    Si no conoces estos datos, puedes dejar los valores por defecto.
                </p>
            """, unsafe_allow_html=True)

            col6, col7, col8 = st.columns(3)
            with col6:
                tipo_equipo = st.selectbox("Tipo de equipo", opciones("TIPO_DE_EQUIPO"))
            # --- MANIOBRAS: comentado hasta tener datos ---
            # with col7:
            #     maniobras = st.selectbox("Maniobras", opciones("MANIOBRAS"))
            # --- ACCESORIALES: comentado hasta tener datos ---
            # with col8:
            #     accesoriales = st.selectbox("Accesoriales", opciones("ACCESORIALES"))

        cotizar = st.form_submit_button("Cotizar", use_container_width=True)

    if cotizar:
        X_nuevo = pd.DataFrame([{
            "TIPO_DE_EQUIPO": encode("TIPO_DE_EQUIPO", tipo_equipo),
            "CLIENTE":        encode("CLIENTE",        cliente),
            "FLUJO":          encode("FLUJO",          flujo),
            "RANGO":          encode("RANGO",          rango),
            "COSTO_EN_MXN":   0,
            "ORIGEN_ESTADO":  encode("ORIGEN_ESTADO",  origen_est),
            "DESTINO_ESTADO": encode("DESTINO_ESTADO", destino_est),
            # --- MANIOBRAS: agregar cuando haya datos ---
            # "MANIOBRAS":      encode("MANIOBRAS",      maniobras),
            # --- ACCESORIALES: agregar cuando haya datos ---
            # "ACCESORIALES":   encode("ACCESORIALES",   accesoriales),
        }])
        X_nuevo = X_nuevo[payload["features"]]
        costo   = float(modelo.predict(X_nuevo)[0])
        venta   = costo * 1.13

        ss["ultima_cotizacion"] = {
            "cliente":        cliente,
            "origen":         origen_est,
            "destino":        destino_est,
            "tipo_equipo":    tipo_equipo,
            "flujo":          flujo,
            "rango":          rango,
            "costo_estimado": round(costo, 2),
            "rango_min":      round(max(0, costo - mae), 2),
            "rango_max":      round(costo + mae, 2),
            "venta_estimada": round(venta, 2),
            "venta_min":      round(max(0, costo - mae) * 1.13, 2),
            "venta_max":      round((costo + mae) * 1.13, 2),
        }

    if "ultima_cotizacion" in ss:
        c = ss["ultima_cotizacion"]

        st.markdown(f"""
            <div class="fli-card">
                <h3>Resultado de la cotizacion</h3>
                <p><b>Cliente:</b> {c['cliente']}</p>
                <p><b>Ruta:</b> {c['origen']} &rarr; {c['destino']}</p>
                <p><b>Equipo:</b> {c['tipo_equipo']} &nbsp;|&nbsp;
                   <b>Flujo:</b> {c['flujo']} &nbsp;|&nbsp;
                   <b>Rango:</b> {c['rango']}</p>
                <hr style="border-color:#6b5b95; margin: 0.8rem 0;">
                <p style="font-size:1.3rem;">
                    <b>Costo estimado:</b>
                    ${c['rango_min']:,.0f} &mdash; ${c['rango_max']:,.0f} MXN
                </p>
                <p style="color:#555; font-size:0.85rem;">
                    Punto medio: ${c['costo_estimado']:,.0f} MXN
                </p>
                <hr style="border-color:#6b5b95; margin: 0.8rem 0;">
                <p style="font-size:1.3rem;">
                    <b>Venta estimada (Utilidad 13%):</b>
                    ${c['venta_min']:,.0f} &mdash; ${c['venta_max']:,.0f} MXN
                </p>
                <p style="color:#555; font-size:0.85rem;">
                    Punto medio: ${c['venta_estimada']:,.0f} MXN
                </p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Guardar ticket")
        tickets_df = cargar_tickets()
        folio      = siguiente_folio(tickets_df)
        fecha_hoy  = datetime.now(pytz.timezone("America/Mexico_City")).strftime("%Y-%m-%d")
        st.write(f"Folio asignado: **{folio}**  |  Fecha: **{fecha_hoy}**")

        if st.button("Guardar ticket"):
            nuevo = {
                "folio":          folio,
                "fecha":          fecha_hoy,
                "usuario":        ss.usuario,
                "cliente":        c["cliente"],
                "origen_estado":  c["origen"],
                "destino_estado": c["destino"],
                "tipo_equipo":    c["tipo_equipo"],
                "flujo":          c["flujo"],
                "rango":          c["rango"],
                "costo_estimado": c["costo_estimado"],
                "costo_final":    c["costo_estimado"],
                "venta_estimada": c["venta_estimada"],
                "venta_final":    c["venta_estimada"],
                "estatus":        "Pendiente",
            }
            tickets_df = pd.concat([tickets_df, pd.DataFrame([nuevo])], ignore_index=True)
            guardar_tickets(tickets_df)
            st.success(f"Ticket {folio} guardado correctamente.")

            pdf_bytes = _generar_pdf({
                **nuevo,
                "rango_min": c["rango_min"],
                "rango_max": c["rango_max"],
                "venta_min": c["venta_min"],
                "venta_max": c["venta_max"],
            })
            st.download_button(
                label="Descargar ticket PDF",
                data=pdf_bytes,
                file_name=f"ticket_{folio}.pdf",
                mime="application/pdf"
            )
            del ss["ultima_cotizacion"]

def tickets_page():
    _header_with_logout("Tickets de Cotizacion", "Revisa, edita y aprueba los tickets generados por los coordinadores.")

    tickets_df = cargar_tickets()

    if tickets_df.empty:
        st.info("No hay tickets registrados aun.")
        return

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_estatus = st.selectbox("Filtrar por estatus",
            ["Todos"] + sorted(tickets_df["estatus"].unique().tolist()))
    with col2:
        filtro_cliente = st.selectbox("Filtrar por cliente",
            ["Todos"] + sorted(tickets_df["cliente"].unique().tolist()))
    with col3:
        filtro_fecha = st.selectbox("Filtrar por fecha",
            ["Todas"] + sorted(tickets_df["fecha"].unique().tolist(), reverse=True))

    df = tickets_df.copy()
    if filtro_estatus != "Todos":
        df = df[df["estatus"] == filtro_estatus]
    if filtro_cliente != "Todos":
        df = df[df["cliente"] == filtro_cliente]
    if filtro_fecha != "Todas":
        df = df[df["fecha"] == filtro_fecha]

    st.markdown(f"**{len(df)} ticket(s) encontrados**")

    columnas_vista = [
    "folio", "fecha", "usuario", "cliente",
    "origen_estado", "destino_estado", "tipo_equipo",
    "costo_estimado", "costo_final",
    "venta_estimada", "venta_final",
    "estatus"
]
    st.dataframe(df[columnas_vista].reset_index(drop=True), use_container_width=True)

    # Descarga Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df[columnas_vista].to_excel(writer, index=False, sheet_name="Tickets")
    st.download_button("Descargar tabla en Excel", buf.getvalue(),
        file_name="tickets_fli.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    st.markdown("#### Editar ticket")

    folio_sel = st.selectbox("Selecciona un folio para editar", df["folio"].tolist())

    if folio_sel:
        idx    = tickets_df[tickets_df["folio"] == folio_sel].index[0]
        ticket = tickets_df.loc[idx]

        # Asegurar que la columna estatus en CSVs viejos
        if "estatus_cobro" not in tickets_df.columns:
            tickets_df["estatus_cobro"] = "Por cobrar"

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
                <p><b>Costo estimado:</b> ${float(ticket['costo_estimado']):,.2f} MXN</p>
                <p><b>Costo final:</b> ${float(ticket['costo_final']):,.2f} MXN</p>
                <p><b>Venta estimada:</b> ${float(ticket['venta_estimada']):,.2f} MXN</p>
                <p><b>Venta final:</b> ${float(ticket['venta_final']):,.2f} MXN</p>
            </div>
        """, unsafe_allow_html=True)

        # Si ya fue cobrado, bloquear edicion 
        if ticket.get("estatus_cobro") == "Cobrado":
            st.warning("Este ticket ya fue cobrado y no puede modificarse.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                costo_final = st.number_input(
                    "Costo final (MXN)", min_value=0.0,
                    value=float(ticket["costo_final"]), step=500.0, format="%.2f")
                venta_final = st.number_input(
                    "Venta final (MXN)", min_value=0.0,
                    value=float(ticket["venta_final"]),
                    step=500.0, format="%.2f")
            with col_b:
                opciones_est = ["Pendiente", "Aprobado", "Rechazado"]
                estatus = st.selectbox("Estatus", opciones_est,
                    index=opciones_est.index(ticket["estatus"])
                    if ticket["estatus"] in opciones_est else 0)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("Guardar cambios"):
                    tickets_df.at[idx, "costo_final"] = costo_final
                    tickets_df.at[idx, "venta_final"] = venta_final
                    tickets_df.at[idx, "estatus"]     = estatus
                    guardar_tickets(tickets_df)
                    st.success("Cambios guardados correctamente.")
                    import time; time.sleep(1.5)
                    st.rerun()
            with col_btn2:
                st.download_button(
                    label="Descargar ticket PDF",
                    data=_generar_pdf(ticket.to_dict()),
                    file_name=f"ticket_{folio_sel}.pdf",
                    mime="application/pdf"
                )


def cobranza_page():
    _header_with_logout("Cobranza", "Seguimiento de tickets pendientes de cobro.")

    tickets_df = cargar_tickets()

    if tickets_df.empty:
        st.info("No hay tickets registrados aun.")
        return

    # Asegurar que la columna existe en CSVs viejos
    if "estatus_cobro" not in tickets_df.columns:
        tickets_df["estatus_cobro"] = "Por cobrar"

    clientes = ["Todos"] + sorted(tickets_df["cliente"].unique().tolist())
    cliente_sel = st.selectbox("Selecciona un cliente", clientes)

    df = tickets_df.copy()
    if cliente_sel != "Todos":
        df = df[df["cliente"] == cliente_sel]


    por_cobrar = df[df["estatus_cobro"] != "Cobrado"].copy()
    cobrados   = df[df["estatus_cobro"] == "Cobrado"].copy()

    with st.expander(f"Tickets por cobrar ({len(por_cobrar)})", expanded=True):
        if por_cobrar.empty:
            st.markdown(f"""
                <div style="background-color:#f0faf4; border-left: 4px solid #2e7d52;
                            padding: 1rem 1.5rem; border-radius: 8px;">
                    <p style="margin:0; font-size:1.2rem; color:#2e7d52;">
                        <b>✓ Al corriente con pagos</b>
                        {"— " + cliente_sel if cliente_sel != "Todos" else ""}
                    </p>
                </div>
            """, unsafe_allow_html=True)

            # Mostrar todos sus tickets aunque estén cobrados
            if not cobrados.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                columnas_cobro = [
                    "folio", "fecha", "cliente",
                    "origen_estado", "destino_estado",
                    "venta_final", "estatus_cobro"
                ]
                st.dataframe(
                    cobrados[columnas_cobro].reset_index(drop=True),
                    use_container_width=True
                )
        else:
            columnas_cobro = [
                "folio", "fecha", "cliente",
                "origen_estado", "destino_estado",
                "venta_final", "estatus_cobro"
            ]
            st.dataframe(
                por_cobrar[columnas_cobro].reset_index(drop=True),
                use_container_width=True
            )

            total = por_cobrar["venta_final"].sum()
            st.markdown(f"""
                <div style="background-color:#f5f3fa; border-left: 4px solid #6b5b95;
                            padding: 1rem 1.5rem; border-radius: 8px; margin-top: 1rem;">
                    <p style="margin:0; font-size:1.3rem; color:#6b5b95;">
                        <b>Total por cobrar:</b> ${total:,.2f} MXN
                    </p>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Registrar pago")

    folios_por_cobrar = por_cobrar["folio"].tolist()

    if not folios_por_cobrar:
        st.info("No hay tickets pendientes para este cliente.")
        return

    folio_sel = st.selectbox("Selecciona folio a marcar", folios_por_cobrar)

    if folio_sel:
        idx    = tickets_df[tickets_df["folio"] == folio_sel].index[0]
        ticket = tickets_df.loc[idx]

        st.markdown(f"""
            <div class="fli-card">
                <h3>Ticket {ticket['folio']}</h3>
                <p><b>Cliente:</b> {ticket['cliente']}</p>
                <p><b>Ruta:</b> {ticket['origen_estado']} &rarr; {ticket['destino_estado']}</p>
                <p><b>Venta final:</b> ${float(ticket['venta_final']):,.2f} MXN</p>
                <p><b>Estatus cobro:</b> {ticket['estatus_cobro']}</p>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            nuevo_estatus_cobro = st.selectbox(
                "Estatus de cobro",
                ["Por cobrar", "En proceso", "Cobrado"],
                index=["Por cobrar", "En proceso", "Cobrado"].index(ticket["estatus_cobro"])
                      if ticket["estatus_cobro"] in ["Por cobrar", "En proceso", "Cobrado"] else 0
            )
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Guardar estatus", use_container_width=True):
                tickets_df.at[idx, "estatus_cobro"] = nuevo_estatus_cobro
                guardar_tickets(tickets_df)
                st.success("Estatus actualizado correctamente.")
                import time; time.sleep(1.5)
                st.rerun()

    
    with st.expander(f"Tickets cobrados ({len(cobrados)})"):
        if cobrados.empty:
            st.info("Aun no hay tickets cobrados.")
        else:
            columnas_cobro = [
                "folio", "fecha", "cliente",
                "origen_estado", "destino_estado",
                "venta_final", "estatus_cobro"
            ]
            st.dataframe(
                cobrados[columnas_cobro].reset_index(drop=True),
                use_container_width=True
            )
            total_cobrado = cobrados["venta_final"].sum()
            st.markdown(f"""
                <div style="background-color:#f0faf4; border-left: 4px solid #2e7d52;
                            padding: 1rem 1.5rem; border-radius: 8px; margin-top: 1rem;">
                    <p style="margin:0; font-size:1.3rem; color:#2e7d52;">
                        <b>Total cobrado:</b> ${total_cobrado:,.2f} MXN
                    </p>
                </div>
            """, unsafe_allow_html=True)

def modelado_page(): # with claude
    import subprocess, json, tempfile, os
 
    _header_with_logout(
        "Modelado", 
        "KPIs operacionales, desempeño del modelo y reentrenamiento."
    )
 
    tickets_df = cargar_tickets()
 
    
    st.markdown("## KPIs Operacionales")
 
    LOADBOARD_PATH = Path("trials/Loadboard.csv")
    if not LOADBOARD_PATH.exists():
        st.warning("No se encontró Loadboard.csv en el directorio raíz.")
    else:
        try:
            lb = pd.read_csv(LOADBOARD_PATH)
 
            # Clean numeric columns
            for col in ["VENTA EN MXN", "COSTO EN MXN", "UTILIDAD EN MXN"]:
                if col in lb.columns:
                    lb[col] = (
                        lb[col].astype(str)
                               .str.replace(r"[\$,]", "", regex=True)
                               .str.strip()
                    )
                    lb[col] = pd.to_numeric(lb[col], errors="coerce")
 
            total_cargas    = len(lb)
            cargas_activas  = lb[lb["ESTATUS"].isin(["Available", "Dispatched",
                                                      "In Transit", "Booked"])].shape[0] \
                              if "ESTATUS" in lb.columns else 0
            venta_total     = lb["VENTA EN MXN"].sum()   if "VENTA EN MXN"    in lb.columns else 0
            costo_total     = lb["COSTO EN MXN"].sum()   if "COSTO EN MXN"    in lb.columns else 0
            utilidad_total  = lb["UTILIDAD EN MXN"].sum() if "UTILIDAD EN MXN" in lb.columns else 0
            margen_pct      = (utilidad_total / venta_total * 100) if venta_total > 0 else 0
 
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Total cargas",    f"{total_cargas:,}")
            k2.metric("Cargas activas",  f"{cargas_activas:,}")
            k3.metric("Venta total",     f"${venta_total/1e6:,.1f}M MXN")
            k4.metric("Costo total",     f"${costo_total/1e6:,.1f}M MXN")
            k5.metric("Margen promedio", f"{margen_pct:.1f}%")
 
            # Top 10 clientes por venta
            if "Cliente" in lb.columns and "VENTA EN MXN" in lb.columns:
                st.markdown("#### Top 10 clientes por venta")
                top = (lb.groupby("Cliente")["VENTA EN MXN"]
                         .sum()
                         .sort_values(ascending=False)
                         .head(10)
                         .reset_index())
                top.columns = ["Cliente", "Venta MXN"]
                top["Venta MXN"] = top["Venta MXN"].map("${:,.0f}".format)
                st.dataframe(top, use_container_width=True, hide_index=True)
 
        except Exception as e:
            st.error(f"Error leyendo Loadboard.csv: {e}")
 
    st.markdown("---")
 
    
    st.markdown("## Desempeño del Modelo")
 
    # Only tickets where we have both prediction and real value
    perf_df = tickets_df[
        tickets_df["costo_estimado"].notna() &
        tickets_df["costo_final"].notna() &
        (tickets_df["costo_final"] > 0) &
        tickets_df["venta_estimada"].notna() &
        tickets_df["venta_final"].notna() &
        (tickets_df["venta_final"] > 0)
    ].copy()
 
    if perf_df.empty:
        st.info("Aún no hay suficientes tickets cerrados para evaluar el modelo.")
    else:
        from sklearn.metrics import (
            mean_absolute_error, mean_absolute_percentage_error,
            root_mean_squared_error
        )
 
        # Costo metrics
        mae_c  = mean_absolute_error(perf_df["costo_final"], perf_df["costo_estimado"])
        mape_c = mean_absolute_percentage_error(perf_df["costo_final"],
                                                 perf_df["costo_estimado"]) * 100
        rmse_c = root_mean_squared_error(perf_df["costo_final"], perf_df["costo_estimado"])
 
        # Venta metrics
        mae_v  = mean_absolute_error(perf_df["venta_final"], perf_df["venta_estimada"])
        mape_v = mean_absolute_percentage_error(perf_df["venta_final"],
                                                 perf_df["venta_estimada"]) * 100
        rmse_v = root_mean_squared_error(perf_df["venta_final"], perf_df["venta_estimada"])
 
        st.markdown(f"**Tickets evaluados: {len(perf_df)}**")
 
        col_c, col_v = st.columns(2)
        with col_c:
            st.markdown("#### Costo estimado vs real")
            c1, c2, c3 = st.columns(3)
            c1.metric("MAE",  f"${mae_c:,.0f}")
            c2.metric("MAPE", f"{mape_c:.1f}%")
            c3.metric("RMSE", f"${rmse_c:,.0f}")
        with col_v:
            st.markdown("#### Venta estimada vs real")
            v1, v2, v3 = st.columns(3)
            v1.metric("MAE",  f"${mae_v:,.0f}")
            v2.metric("MAPE", f"{mape_v:.1f}%")
            v3.metric("RMSE", f"${rmse_v:,.0f}")
 
        # Drift warning — if MAPE > 15%, suggest retraining
        MAPE_THRESHOLD = 15.0
        needs_retrain  = mape_c > MAPE_THRESHOLD or mape_v > MAPE_THRESHOLD
 
        if needs_retrain:
            st.markdown(f"""
                <div style="background-color:#fff3cd; border-left:4px solid #e6a817;
                            padding:1rem 1.5rem; border-radius:8px; margin-top:1rem;">
                    <p style="margin:0; font-size:1.05rem; color:#856404;">
                        ⚠️ <b>Las predicciones han perdido precisión</b>
                        (MAPE costo: {mape_c:.1f}% | MAPE venta: {mape_v:.1f}% —
                        umbral: {MAPE_THRESHOLD}%).
                        Se recomienda reentrenar el modelo.
                    </p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div style="background-color:#d4edda; border-left:4px solid #28a745;
                            padding:1rem 1.5rem; border-radius:8px; margin-top:1rem;">
                    <p style="margin:0; font-size:1.05rem; color:#155724;">
                        ✓ El modelo está dentro del umbral de precisión
                        (MAPE costo: {mape_c:.1f}% | MAPE venta: {mape_v:.1f}%).
                    </p>
                </div>
            """, unsafe_allow_html=True)
 
    st.markdown("---")
 
    
    st.markdown("## Reentrenar Modelo")
 
    # Step 1: choose data source
    if "retrain_source" not in ss:
        ss.retrain_source = None
    if "retrain_csv_path" not in ss:
        ss.retrain_csv_path = None
    if "retrain_confirmed" not in ss:
        ss.retrain_confirmed = False
 
    st.markdown("#### Paso 1 — Fuente de datos")
    fuente = st.radio(
        "¿Con qué datos deseas reentrenar?",
        ["Datos de la plataforma (histórico + tickets cerrados)",
         "Subir CSV propio"],
        index=0,
        key="radio_fuente",
    )
    source_key = "platform" if fuente.startswith("Datos") else "csv"
 
    uploaded_csv_path = None
    if source_key == "csv":
        uploaded_file = st.file_uploader(
            "Sube el CSV de entrenamiento",
            type=["csv"],
            key="retrain_upload",
        )
        if uploaded_file is not None:
            # Save to a temp file so subprocess can read it
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".csv", prefix="retrain_"
            )
            tmp.write(uploaded_file.read())
            tmp.close()
            uploaded_csv_path = tmp.name
            st.success(f"Archivo cargado: {uploaded_file.name} "
                       f"({uploaded_file.size / 1024:.1f} KB)")
 
    # Step 2: password confirmation
    st.markdown("#### Paso 2 — Confirmación de seguridad")
    retrain_password = st.text_input(
        "Ingresa la contraseña para confirmar el reentrenamiento",
        type="password",
        key="retrain_pwd",
    )
 
    RETRAIN_PASSWORD = USUARIOS.get("modelado", {}).get("password", "")
 
    ready_to_run = (
        retrain_password == RETRAIN_PASSWORD and retrain_password != ""
        and (source_key == "platform" or uploaded_csv_path is not None)
    )
 
    if retrain_password and retrain_password != RETRAIN_PASSWORD:
        st.error("Contraseña incorrecta.")
 
    # run
    st.markdown("#### Paso 3 — Ejecutar reentrenamiento")
 
    if not ready_to_run:
        st.button("Reentrenar modelo", disabled=True,
                  help="Completa los pasos anteriores para habilitar.")
    else:
        if st.button(" Reentrenar modelo", type="primary"):
            script_path = Path("trials/model_implementation.py").resolve()
 
            cmd = [sys.executable, str(script_path), "--source", source_key]
            if source_key == "csv" and uploaded_csv_path:
                cmd += ["--csv_path", uploaded_csv_path]
 
            with st.spinner("Entrenando modelo... esto puede tomar unos minutos."):
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=600,
                    )
                    # Parse the JSON output line
                    output_lines = result.stdout.strip().splitlines()
                    last_line    = output_lines[-1] if output_lines else "{}"
                    data         = json.loads(last_line)
 
                    if data.get("status") == "ok":
                        # Invalidate cached model so next cotizacion loads the new one
                        if "modelo_payload" in ss:
                            del ss["modelo_payload"]
 
                        st.success(
                            f" Modelo reentrenado exitosamente.\n\n"
                            f"**MAE:** ${data['mae']:,.0f} MXN  |  "
                            f"**RMSE:** ${data['rmse']:,.0f} MXN  |  "
                            f"**Filas usadas:** {data['n_rows']:,}"
                        )
                        st.markdown(f"""
                            <div style="background-color:#d4edda; border-left:4px solid #28a745;
                                        padding:1rem 1.5rem; border-radius:8px;">
                                <p style="margin:0; color:#155724;">
                                    El modelo anterior fue archivado y el nuevo está activo
                                    como <b>modelo_final.pkl</b>.
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error(f"Error durante el reentrenamiento: "
                                 f"{data.get('message', 'Desconocido')}")
                        if result.stderr:
                            with st.expander("Ver detalle del error"):
                                st.code(result.stderr)
 
                except subprocess.TimeoutExpired:
                    st.error("El reentrenamiento tardó demasiado (>10 min). "
                             "Verifica los datos e intenta nuevamente.")
                except json.JSONDecodeError:
                    st.error("Error parseando la salida del script.")
                    with st.expander("Ver salida del script"):
                        st.code(result.stdout)
                        st.code(result.stderr)
                finally:
                    # Clean up temp CSV
                    if uploaded_csv_path and os.path.exists(uploaded_csv_path):
                        os.unlink(uploaded_csv_path)
 


def _generar_pdf(datos: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(107, 91, 149)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, "FLI Cotizador - Ticket de Cotizacion", ln=True, fill=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(107, 91, 149)
    pdf.ln(6)

    costo_final = datos.get("costo_final", datos.get("costo_estimado", 0))
    venta_final = datos.get("venta_final", datos.get("venta_estimada", 0))
    campos = [
        ("Folio",             datos.get("folio", "")),
        ("Fecha",             datos.get("fecha", "")),
        ("Generado por",      datos.get("usuario", "")),
        ("Cliente",           datos.get("cliente", "")),
        ("Estado de origen",  datos.get("origen_estado", "")),
        ("Estado de destino", datos.get("destino_estado", "")),
        ("Tipo de equipo",    datos.get("tipo_equipo", "")),
        ("Flujo",             datos.get("flujo", "")),
        ("Rango",             datos.get("rango", "")),
        ("Costo estimado",   f"${float(datos.get('costo_estimado', 0)):,.2f} MXN"),
        ("Costo final",      f"${float(costo_final):,.2f} MXN"),
        ("Venta estimada",   f"${float(datos.get('venta_estimada', 0)):,.2f} MXN"),
        ("Venta final",      f"${float(venta_final):,.2f} MXN"),
        ("Estatus",           datos.get("estatus", "Pendiente")),
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


if "runpage" not in ss:
    ss.runpage = login_page

ss.runpage()




# COBRANZA
# TO DO
# if rechazado por ventas
# NOT in COBRANZA, NOT IN TRAINNIN BASE


# MODELADO
# TO DO:
# - banner con: 
#   - KPIS
#   - Desempeño del modelo
#       * Desempeño del modelo MAE
#       * Dividir con color Venta y Costo
#       * posible cambiar mae tolerancia y guardarla en variable e imprimirla en automático
#       * boton ¿Reentrenar modelo?
#               + click, rederect retrain model, go back
#
#
# RETRAIN MODEL
# - fuente de datos
#       - tickets hechos
#       - csv proprio
# tick box : añadir histórico?
#       - add si sí no add si no
# hacer training
# if peor, anunciar que es peor y no cambiar
# if mejor
# cambiar a current, anexar tickets a histórico
