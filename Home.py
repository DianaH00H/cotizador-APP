import streamlit as st
from utils import aplicar_estilo, USUARIOS

st.set_page_config(
    page_title="FLI Cotizador",
    page_icon=None,
    layout="centered"
)

aplicar_estilo()

# ------------------------------------------------------------------
# Inicializar estado de sesion
# ------------------------------------------------------------------
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "rol" not in st.session_state:
    st.session_state.rol = None

# ------------------------------------------------------------------
# Si ya hay sesion activa mostrar bienvenida y boton de cerrar sesion
# ------------------------------------------------------------------
if st.session_state.usuario:
    st.markdown(f"""
        <div class="fli-header">
            <h1>FLI Cotizador</h1>
            <p>Bienvenido, {st.session_state.usuario} — Rol: {st.session_state.rol}</p>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.rol == "carrier":
        st.info("Usa el menu lateral para ir a Nueva Cotizacion.")
    else:
        st.info("Usa el menu lateral para ir a Tickets.")

    if st.button("Cerrar sesion"):
        st.session_state.usuario = None
        st.session_state.rol = None
        st.rerun()

    st.stop()

# ------------------------------------------------------------------
# Pantalla de login
# ------------------------------------------------------------------
st.markdown("""
    <div style="text-align:center; padding: 2rem 0 1rem 0;">
        <div style="background-color:#0A2342; display:inline-block;
                    padding: 1.5rem 3rem; border-radius: 10px;">
            <h1 style="color:#FFFFFF; margin:0; font-size:2rem;">FLI Cotizador</h1>
            <p style="color:#A8C4E0; margin:0.3rem 0 0 0;">
                Sistema de cotizacion de fletes
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

with st.form("login_form"):
    usuario    = st.text_input("Usuario")
    contrasena = st.text_input("Contrasena", type="password")
    entrar     = st.form_submit_button("Entrar")

if entrar:
    if usuario in USUARIOS and USUARIOS[usuario]["password"] == contrasena:
        st.session_state.usuario = usuario
        st.session_state.rol     = USUARIOS[usuario]["rol"]
        st.success(f"Bienvenido, {usuario}.")
        st.rerun()
    else:
        st.error("Usuario o contrasena incorrectos.")
