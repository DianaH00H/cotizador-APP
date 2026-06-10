import argparse
import json
import pickle
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, RandomizedSearchCV, cross_val_score
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------
# Parte 2. Entrenamiento y seleccion del mejor modelo
# Objetivo: tunear XGBoost con RandomizedSearchCV + Cross Validation,
# y guardar el mejor modelo.
# Todos los archivos viven en el mismo directorio que este script.
# ------------------------------------------------------------------



# ADJUSTMENTS MADE WITH CLAUDE
BASE_DIR    = Path(__file__).parent
DATA_PATH   = BASE_DIR / "datos_modelo.pkl"
TICKETS_CSV = BASE_DIR / "tickets.csv"
MODEL_PATH  = BASE_DIR / "modelo_final.pkl"


def cargar_datos(path: Path):
    with open(path, "rb") as f:
        payload = pickle.load(f)

    df       = payload["df"]
    features = payload["features"]
    target   = payload["target"]
    encoders = payload["encoders"]

    X = df[features]
    y = df[target]

    print(f"Datos cargados: {X.shape[0]} registros, {X.shape[1]} features")
    return X, y, encoders, features, payload


def _tickets_a_filas(tickets_path: Path, features: list,
                     target: str, encoders: dict) -> pd.DataFrame:
    """
    Convierte tickets cerrados (costo_final > 0) en filas de entrenamiento
    usando los encoders existentes para mantener consistencia.
    """
    df = pd.read_csv(tickets_path)
    df = df[df["costo_final"].notna() & (df["costo_final"] > 0)].copy()
    if df.empty:
        return pd.DataFrame()

    rename = {
        "tipo_equipo":    "TIPO_DE_EQUIPO",
        "cliente":        "CLIENTE",
        "flujo":          "FLUJO",
        "rango":          "RANGO",
        "origen_estado":  "ORIGEN_ESTADO",
        "destino_estado": "DESTINO_ESTADO",
        "costo_final":    target,
    }
    df = df.rename(columns=rename)

    for col, le in encoders.items():
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x if x in le.classes_ else "Desconocido"
            )
            df[col] = le.transform(df[col])

    if "COSTO_EN_MXN" in features and "COSTO_EN_MXN" not in df.columns:
        df["COSTO_EN_MXN"] = 0

    cols = features + [target]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"  Tickets: columnas faltantes {missing}, se omiten.")
        return pd.DataFrame()

    return df[cols].dropna()


def _csv_a_filas(csv_path: Path, features: list,
                 target: str, encoders: dict) -> pd.DataFrame:
    """
    Carga un CSV externo, normaliza columnas y codifica categoricas.
    Acepta el schema de Loadboard.csv o cualquier CSV con columnas equivalentes.
    """
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().upper().replace(" ", "_") for c in df.columns]

    col_map = {
        "COSTO":       "COSTO_EN_MXN",
        "ORIGEN":      "ORIGEN_ESTADO",
        "DESTINO":     "DESTINO_ESTADO",
        "TIPO_EQUIPO": "TIPO_DE_EQUIPO",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    if "COSTO_EN_MXN" in df.columns:
        df["COSTO_EN_MXN"] = (
            df["COSTO_EN_MXN"].astype(str)
                              .str.replace(r"[\$,]", "", regex=True)
                              .str.strip()
        )
        df["COSTO_EN_MXN"] = pd.to_numeric(df["COSTO_EN_MXN"], errors="coerce")

    for col, le in encoders.items():
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x if x in le.classes_ else "Desconocido"
            )
            df[col] = le.transform(df[col])

    if "COSTO_EN_MXN" in features and "COSTO_EN_MXN" not in df.columns:
        df["COSTO_EN_MXN"] = 0

    cols = features + [target]
    available = [c for c in cols if c in df.columns]
    df = df[available].dropna()
    df = df[df[target] > 0]
    return df[cols] if len(df) > 0 and all(c in df.columns for c in cols) \
           else pd.DataFrame()


def evaluar(nombre, modelo, X_test, y_test):
    y_pred = modelo.predict(X_test)
    mae    = mean_absolute_error(y_test, y_pred)
    rmse   = root_mean_squared_error(y_test, y_pred)
    r2     = r2_score(y_test, y_pred)
    print(f"  {nombre:<20} MAE: ${mae:,.0f}   RMSE: ${rmse:,.0f}   R2: {r2:.4f}")
    return {"nombre": nombre, "modelo": modelo, "mae": mae, "rmse": rmse, "r2": r2}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["platform", "csv"], default="platform")
    parser.add_argument("--csv_path", default=None)
    args = parser.parse_args()

    # ── Cargar datos base ─────────────────────────────────────────
    X, y, encoders, features, payload = cargar_datos(DATA_PATH)
    target = payload["target"]

    # ── Combinar con datos adicionales ────────────────────────────
    if args.source == "platform":
        print("Fuente: plataforma (datos_modelo.pkl + tickets.csv)")
        extra = _tickets_a_filas(TICKETS_CSV, features, target, encoders)
        if not extra.empty:
            X = pd.concat([X, extra[features]], ignore_index=True)
            y = pd.concat([y, extra[target]],   ignore_index=True)
            print(f"  +{len(extra)} filas de tickets. Total: {len(X)}")
        else:
            print("  No se encontraron tickets cerrados utilizables.")

    elif args.source == "csv":
        if not args.csv_path:
            print(json.dumps({"status": "error",
                              "message": "--csv_path requerido para source=csv"}))
            sys.exit(1)
        print(f"Fuente: CSV externo ({args.csv_path})")
        extra = _csv_a_filas(Path(args.csv_path), features, target, encoders)
        if not extra.empty:
            X = extra[features]
            y = extra[target]
            print(f"  {len(X)} filas cargadas del CSV.")
        else:
            print(json.dumps({"status": "error",
                              "message": "El CSV no contiene filas validas."}))
            sys.exit(1)

    # ── Split ─────────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"\nTrain: {len(X_train)} registros | Test: {len(X_test)} registros\n")

    # ── XGBoost + RandomizedSearchCV (igual que el original) ──────
    xgb_params = {
        "n_estimators":     [100, 200, 300, 500],
        "max_depth":        [3, 5, 7, 9],
        "learning_rate":    [0.01, 0.05, 0.1, 0.2],
        "subsample":        [0.6, 0.8, 1.0],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "min_child_weight": [1, 3, 5],
    }

    xgb_search = RandomizedSearchCV(
        XGBRegressor(random_state=42, verbosity=0),
        param_distributions=xgb_params,
        n_iter=30,
        cv=5,
        scoring="neg_mean_absolute_error",
        random_state=42,
        n_jobs=1,       # n_jobs=1: evita crash de multiprocessing en macOS Python 3.13
        verbose=1,
    )

    print("Tuneando XGBoost...")
    xgb_search.fit(X_train, y_train)
    print(f"\nMejores parametros XGBoost: {xgb_search.best_params_}")

    mejor_modelo = xgb_search.best_estimator_
    resultados   = [evaluar("XGBoost", mejor_modelo, X_test, y_test)]

    # ── Resultado final + CV ──────────────────────────────────────
    print("\n--- Resultado final ---")
    for r in resultados:
        print(f"  {r['nombre']:<20} MAE: ${r['mae']:,.0f}   RMSE: ${r['rmse']:,.0f}   R2: {r['r2']:.4f}")

    cv_scores = cross_val_score(
        mejor_modelo, X, y,
        cv=5, scoring="neg_mean_absolute_error", n_jobs=1,
    )
    print(f"\nCV MAE promedio: ${-cv_scores.mean():,.0f} (+/- ${cv_scores.std():,.0f})")

    # ── Archivar modelo anterior ──────────────────────────────────
    if MODEL_PATH.exists():
        date_str = datetime.now().strftime("%Y-%m-%d")
        archive  = MODEL_PATH.parent / f"model_{date_str}.pkl"
        suffix   = 0
        while archive.exists():
            suffix += 1
            archive = MODEL_PATH.parent / f"model_{date_str}_{suffix}.pkl"
        MODEL_PATH.rename(archive)
        print(f"\nModelo anterior archivado como: {archive.name}")

    # ── Guardar nuevo modelo ──────────────────────────────────────
    payload_final = {
        "modelo":   mejor_modelo,
        "nombre":   "XGBoost",
        "encoders": encoders,
        "features": features,
        "metricas": {
            "mae":  resultados[0]["mae"],
            "rmse": resultados[0]["rmse"],
            "r2":   resultados[0]["r2"],
        },
        "fecha":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_rows": int(len(X)),
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(payload_final, f)

    print(f"\nModelo guardado en: {MODEL_PATH}")
    print("Fase 2 completada.")

    # ── JSON para modelado_page (debe ser la ultima linea) ────────
    print(json.dumps({
        "status":     "ok",
        "mae":        round(resultados[0]["mae"],  2),
        "rmse":       round(resultados[0]["rmse"], 2),
        "r2":         round(resultados[0]["r2"],   4),
        "n_rows":     int(len(X)),
        "model_path": str(MODEL_PATH),
    }))


if __name__ == "__main__":
    main()