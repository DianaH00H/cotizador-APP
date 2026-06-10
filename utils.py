import streamlit as st
import pandas as pd
import pickle
from pathlib import Path

# ------------------------------------------------------------------
# Utilidades compartidas entre paginas
# ------------------------------------------------------------------

TICKETS_PATH = Path("trials/tickets.csv")
MODEL_PATH   = Path("trials/modelo_final.pkl")

COLUMNAS_TICKET = [
    "folio", "fecha", "usuario", "cliente",
    "origen_estado", "destino_estado", "tipo_equipo",
    "flujo", "rango",
    "costo_estimado", "costo_final",
    "venta_estimada", "venta_final",
    "estatus", "estatus_cobro"
]

USUARIOS = st.secrets["usuarios"]


def aplicar_estilo():
    st.markdown("""
        <style>
            /* Sidebar */
            [data-testid="stSidebar"] {
                background-color: #6b5b95;
            }
            [data-testid="stSidebar"] * {
                color: #FFFFFF !important;
            }

            /* Botones principales */
            .stButton > button {
                background-color: #EBBA07;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0.5rem 1.5rem;
                font-weight: 600;
                width: 100%;
            }
            .stButton > button:hover {
                background-color: #EBBA07;
                color: #FFFFFF;
            }

            /* Encabezado de pagina */
            .fli-header {
                background-color: #6b5b95;
                color: #FFFFFF;
                padding: 1.2rem 2rem;
                border-radius: 8px;
                margin-bottom: 1.5rem;
            }
            .fli-header h1 {
                color: #FFFFFF;
                margin: 0;
                font-size: 1.6rem;
            }
            .fli-header p {
                color: #A8C4E0;
                margin: 0;
                font-size: 0.9rem;
            }

            /* Tarjeta de resultado */
            .fli-card {
                background-color: #F0F4F8;
                border-left: 5px solid #6b5b95;
                padding: 1rem 1.5rem;
                border-radius: 6px;
                margin: 1rem 0;
            }
            .fli-card h3 {
                color: #6b5b95;
                margin: 0 0 0.5rem 0;
            }
            .fli-card p {
                color: #6b5b95;
                margin: 0.2rem 0;
            }

            /* Ocultar menu de streamlit */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)


def header(titulo: str, subtitulo: str = ""):
    st.markdown(f"""
        <div class="fli-header">
            <h1>FLI Cotizador &nbsp;|&nbsp; {titulo}</h1>
            <p>{subtitulo}</p>
        </div>
    """, unsafe_allow_html=True)


def verificar_login():
    # Verifica que haya sesion activa, si no redirige al login
    if "usuario" not in st.session_state or not st.session_state.usuario:
        st.warning("Debes iniciar sesion primero.")
        st.stop()


def cargar_modelo():
    with open(MODEL_PATH, "rb") as f:
        payload = pickle.load(f)
    return payload


def cargar_tickets() -> pd.DataFrame:
    if TICKETS_PATH.exists():
        return pd.read_csv(TICKETS_PATH)
    return pd.DataFrame(columns=COLUMNAS_TICKET)


def guardar_tickets(df: pd.DataFrame):
    TICKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(TICKETS_PATH, index=False)


def siguiente_folio(df: pd.DataFrame) -> str:
    if df.empty:
        return "FLI-0001"
    ultimo = df["folio"].str.extract(r"(\d+)").astype(int).max().values[0]
    return f"FLI-{ultimo + 1:04d}"
