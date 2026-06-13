"""
Modelo autocontenido para el Cotizador FLI.

Este modulo define `CotizadorPipeline`, un envoltorio que empaqueta en un solo
objeto el modelo XGBoost ya entrenado MAS todo el preprocesamiento que el
modelo necesita. El objetivo es que la interfaz (Streamlit) solo tenga que
pasar las variables PRINCIPALES en crudo (sin encodear) y reciba de vuelta un
resultado limpio: la VENTA_EN_MXN estimada.

Asi la app NO tiene que replicar el One-Hot Encoding, el split de ubicacion ni
el alineado de columnas: todo eso ocurre dentro del .pkl.

Entrada esperada (variables crudas, tal cual las captura el usuario):
    ORIGEN                       str  "Ciudad, Estado"   (ej. "Guadalajara, Jalisco")
    DESTINO                      str  "Ciudad, Estado"   (ej. "Monterrey, Nuevo Leon")
    TIPO_DE_EQUIPO               str  (ej. "DryVan 53")
    FLUJO                        str  (ej. "Southbound")
    RANGO                        str  (ej. "Contracted")
    TIPO_DE_VENTA                str  (ej. "Ordinaria")
    MONTH                        int  1..12
    CANTIDAD_ACCESORIALES_COSTO  num  (default 0)

Salida:
    np.ndarray de floats con la VENTA_EN_MXN estimada (una por fila de entrada).

NOTA: para des-serializar el .pkl, este modulo debe ser importable. Si se usa
fuera de este repo (p. ej. en la app), copiar este archivo junto al .pkl.
"""

import numpy as np
import pandas as pd

# Variables crudas que la interfaz debe entregar al modelo.
VARIABLES_ENTRADA = [
    "ORIGEN",
    "DESTINO",
    "TIPO_DE_EQUIPO",
    "FLUJO",
    "RANGO",
    "TIPO_DE_VENTA",
    "MONTH",
    "CANTIDAD_ACCESORIALES_COSTO",
]

TARGET = "VENTA_EN_MXN"


def _split_location(loc):
    """Separa 'Ciudad, Estado' en sus dos componentes (igual que en entrenamiento)."""
    if pd.isna(loc):
        return pd.Series([np.nan, np.nan])
    parts = [x.strip() for x in str(loc).split(",")]
    if len(parts) >= 2:
        return pd.Series([parts[0], parts[1]])
    return pd.Series([parts[0], np.nan])


class CotizadorPipeline:
    """
    Modelo + preprocesamiento empaquetados juntos.

    Parameters
    ----------
    modelo : estimador entrenado (XGBRegressor) que espera el espacio de
        `columnas_modelo` (361 columnas One-Hot, en ese orden).
    categoricas : list[str] columnas que se One-Hot encodean.
    columnas_modelo : list[str] espacio de features exacto que vio el modelo.
    metricas : dict con metricas del modelo (mae, rmse, ...). Se usa para
        construir un rango de confianza alrededor de la estimacion.
    opciones : dict[str, list] valores validos por variable de entrada, para
        poblar los menus desplegables de la interfaz.
    """

    def __init__(self, modelo, categoricas, columnas_modelo,
                 metricas=None, opciones=None, nombre="XGBoost"):
        self.modelo = modelo
        self.categoricas = list(categoricas)
        self.columnas_modelo = list(columnas_modelo)
        self.metricas = dict(metricas or {})
        self.opciones = dict(opciones or {})
        self.nombre = nombre
        self.target = TARGET
        self.variables_entrada = list(VARIABLES_ENTRADA)

    # ------------------------------------------------------------------
    # Preprocesamiento (replica exacta del entrenamiento, apto para 1+ filas)
    # ------------------------------------------------------------------
    def _preparar(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # 1) Separar ORIGEN / DESTINO en ciudad y estado
        df[["ORIGEN_CIUDAD", "ORIGEN_ESTADO"]] = df["ORIGEN"].apply(_split_location)
        df[["DESTINO_CIUDAD", "DESTINO_ESTADO"]] = df["DESTINO"].apply(_split_location)

        # 2) MONTH como categoria (string)
        df["MONTH"] = df["MONTH"].astype(str)

        # 3) Rellenar nulos de categoricas con 'Desconocido'
        for col in self.categoricas:
            if col not in df.columns:
                df[col] = "Desconocido"
            df[col] = df[col].fillna("Desconocido").astype(str)

        # 4) Variable numerica
        cant = pd.to_numeric(
            df.get("CANTIDAD_ACCESORIALES_COSTO", 0), errors="coerce"
        ).fillna(0)

        # 5) One-Hot manual alineado a columnas_modelo.
        #    Se construye directamente el espacio final para reproducir
        #    drop_first=True de forma robusta con una sola fila: la categoria
        #    de referencia (la que se elimino al entrenar) y las desconocidas
        #    quedan como vector de ceros, que es justo su codificacion.
        out = pd.DataFrame(
            0.0, index=df.index, columns=self.columnas_modelo, dtype="float64"
        )
        if "CANTIDAD_ACCESORIALES_COSTO" in out.columns:
            out["CANTIDAD_ACCESORIALES_COSTO"] = cant.to_numpy()

        col_index = set(self.columnas_modelo)
        for col in self.categoricas:
            dummy = col + "_" + df[col].astype(str)
            for idx, name in zip(df.index, dummy):
                if name in col_index:
                    out.at[idx, name] = 1.0

        return out[self.columnas_modelo]

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def predict(self, datos):
        """
        Predice VENTA_EN_MXN a partir de variables crudas.

        `datos` puede ser un dict (una cotizacion) o un DataFrame/lista de dicts
        (varias). Devuelve siempre un np.ndarray de floats.
        """
        if isinstance(datos, dict):
            datos = pd.DataFrame([datos])
        elif isinstance(datos, list):
            datos = pd.DataFrame(datos)
        X = self._preparar(datos)
        return np.asarray(self.modelo.predict(X), dtype=float)

    def cotizar(self, **kwargs) -> dict:
        """
        Atajo para una sola cotizacion: devuelve un dict limpio y listo para
        mostrar, incluyendo un rango de confianza (+/- MAE).
        """
        venta = float(self.predict(kwargs)[0])
        mae = float(self.metricas.get("mae", 0.0))
        return {
            "venta_estimada": round(venta, 2),
            "rango_min": round(max(0.0, venta - mae), 2),
            "rango_max": round(venta + mae, 2),
            "mae": round(mae, 2),
        }
