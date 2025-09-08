# app_flask.py
# ----------------------------
# API de reportes con Flask + PostgreSQL
# Acepta JSON de la app Flutter (formato viejo y nuevo),
# guarda coordenadas y foto en base64 y muestra un mapa en "/".
# ----------------------------
import psycopg2
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import os
import re

APP_PORT = int(os.getenv("PORT", "8080"))

app = Flask(__name__, template_folder="templates")
CORS(app)

# ----------------------------
# Utilidades de base de datos
# ----------------------------
def get_conn():
    return psycopg2.connect(
        host="flaskdb.cj6u0amymnlu.us-east-2.rds.amazonaws.com", 
        dbname="flaskdb",   
        user="postgres",    
        password="postgres",
        port=5432
    )

def init_db():
    """Crea tabla si no existe."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reportes(
            id SERIAL PRIMARY KEY,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            fecha TEXT,
            foto_base64 TEXT,
            mime TEXT,
            filename TEXT,
            accuracy DOUBLE PRECISION,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# Helpers
# ----------------------------
DATA_URI_RE = re.compile(r"^data:[^;]+;base64,")

def clean_b64(s: str | None) -> str | None:
    if not s:
        return s
    return DATA_URI_RE.sub("", s)

def parse_report_payload(data: dict) -> tuple[dict, list[str]]:
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

    if accuracy is not None:
        try:
            accuracy = float(accuracy)
        except (TypeError, ValueError):
            accuracy = None

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
    if not request.is_json:
        return jsonify({"error": "Content-Type debe ser application/json"}), 415

    data = request.get_json(silent=True) or {}
    payload, errs = parse_report_payload(data)
    if errs:
        return jsonify({"error": "payload inválido", "detalles": errs}), 400

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO reportes(lat, lon, fecha, foto_base64, mime, filename, accuracy, created_at)
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
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
    rid = c.fetchone()[0]
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "id": rid}), 201

@app.get("/reportes")
def listar_reportes():
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
    return render_template("mapa.html")

# ----------------------------
# Arranque
# ----------------------------
application = app


