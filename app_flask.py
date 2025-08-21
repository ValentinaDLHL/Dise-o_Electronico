# app_flask.py
# ----------------------------
# API de reportes con Flask + SQLite
# Acepta JSON de la app Flutter (formato viejo y nuevo),
# guarda coordenadas y foto en base64 y muestra un mapa en "/".
# ----------------------------

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import sqlite3
import os
import re

APP_PORT = int(os.getenv("PORT", "8080"))
DB_FILE = os.getenv("DB_FILE", "reportes.db")

app = Flask(__name__, template_folder="templates")  # ✅ CORREGIDO
# Permitir CORS para cualquier origen (ajústalo si lo necesitas)
CORS(app)

# ----------------------------
# Utilidades de base de datos
# ----------------------------
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    """Crea tabla si no existe y agrega columnas nuevas si faltan."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reportes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL,
            lon REAL,
            fecha TEXT,
            foto_base64 TEXT,
            mime TEXT,
            filename TEXT,
            accuracy REAL,
            created_at TEXT
        )
        """
    )
    conn.commit()

    # Asegura columnas si la DB existía de antes
    c.execute("PRAGMA table_info(reportes)")
    cols = {row[1] for row in c.fetchall()}
    alters = []
    if "mime" not in cols:
        alters.append("ALTER TABLE reportes ADD COLUMN mime TEXT")
    if "filename" not in cols:
        alters.append("ALTER TABLE reportes ADD COLUMN filename TEXT")
    if "accuracy" not in cols:
        alters.append("ALTER TABLE reportes ADD COLUMN accuracy REAL")
    if "created_at" not in cols:
        alters.append("ALTER TABLE reportes ADD COLUMN created_at TEXT")

    for sql in alters:
        c.execute(sql)
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# Helpers
# ----------------------------
DATA_URI_RE = re.compile(r"^data:[^;]+;base64,")

def clean_b64(s: str | None) -> str | None:
    """Quita prefijo data:...;base64, si viene así."""
    if not s:
        return s
    return DATA_URI_RE.sub("", s)

def parse_report_payload(data: dict) -> tuple[dict, list[str]]:
    """
    Normaliza el payload aceptando campos 'viejos' y 'nuevos'.
    Devuelve (payload_normalizado, errores)
    """
    errs: list[str] = []

    def pick(*keys, default=None):
        for k in keys:
            if k in data and data[k] is not None:
                return data[k]
        return default

    lat = pick("lat", "latitude")
    lon = pick("lon", "longitude")
    fecha = pick("fecha", "timestamp", default=datetime.utcnow().isoformat())
    foto_base64 = pick("foto_base64", "photo_base64")
    mime = pick("mime", "photo_mime_type")
    filename = pick("filename", "photo_filename")
    accuracy = pick("accuracy", "accuracy_m")

    # Validaciones básicas
    try:
        lat = float(lat)
    except (TypeError, ValueError):
        errs.append("lat/latitude inválida")
    try:
        lon = float(lon)
    except (TypeError, ValueError):
        errs.append("lon/longitude inválida")

    if not errs:
        if not (-90.0 <= lat <= 90.0):
            errs.append("lat fuera de rango (-90..90)")
        if not (-180.0 <= lon <= 180.0):
            errs.append("lon fuera de rango (-180..180)")

    # Accuracy opcional
    if accuracy is not None:
        try:
            accuracy = float(accuracy)
        except (TypeError, ValueError):
            accuracy = None  # ignorar

    # Higiene base64
    foto_base64 = clean_b64(foto_base64)

    payload = {
        "lat": lat,
        "lon": lon,
        "fecha": str(fecha),
        "foto_base64": foto_base64,
        "mime": mime,
        "filename": filename,
        "accuracy": accuracy,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    return payload, errs

# ----------------------------
# Rutas
# ----------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.post("/reportes")
def crear_reporte():
    """
    Recibe JSON. Ejemplos válidos:
    - Formato viejo:
      {"lat": 10.1, "lon": -74.8, "fecha":"2025-08-20", "foto_base64":"..."}
    - Formato nuevo (Flutter actual):
      {
        "timestamp":"2025-08-20T20:00:00Z",
        "latitude":10.1,"longitude":-74.8,"accuracy_m":12.3,
        "photo_base64":"...","photo_mime_type":"image/jpeg","photo_filename":"x.jpg"
      }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type debe ser application/json"}), 415

    data = request.get_json(silent=True) or {}
    payload, errs = parse_report_payload(data)
    if errs:
        return jsonify({"error": "payload inválido", "detalles": errs}), 400

    # Insertar
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO reportes(lat, lon, fecha, foto_base64, mime, filename, accuracy, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["lat"],
            payload["lon"],
            payload["fecha"],
            payload["foto_base64"],
            payload["mime"],
            payload["filename"],
            payload["accuracy"],
            payload["created_at"],
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "id": rid}), 201

@app.get("/reportes")
def listar_reportes():
    """
    Devuelve todos los reportes (filtrando nulos) ordenados por id DESC.
    Incluye base64 (útil para tu vista web actual).
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, lat, lon, fecha, foto_base64, mime, filename, accuracy, created_at
        FROM reportes
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY id DESC
        """
    )
    rows = c.fetchall()
    conn.close()

    out = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "lat": r[1],
                "lon": r[2],
                "fecha": r[3],
                "foto_base64": r[4],
                "mime": r[5],
                "filename": r[6],
                "accuracy": r[7],
                "created_at": r[8],
            }
        )
    return jsonify(out), 200

@app.delete("/borrar_todos")
def borrar_todos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM reportes")
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "mensaje": "Todos los reportes eliminados"}), 200

@app.get("/")
def home():
    # Renderiza templates/mapa.html (ya existente en tu repo)
    return render_template("mapa.html")

# ----------------------------
# Arranque
# ----------------------------
if __name__ == "__main__":  # ✅ CORREGIDO
    # Escucha en todas las interfaces para que teléfonos en la red o a través de túnel puedan llegar.
    app.run(host="0.0.0.0", port=APP_PORT)