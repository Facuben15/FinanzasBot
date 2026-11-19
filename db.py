import sqlite3
import os
import json

DB_PATH = os.getenv("DB_PATH", "historial.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                rol TEXT NOT NULL,
                contenido TEXT NOT NULL,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        c.execute(
            """CREATE TABLE IF NOT EXISTS pasos_gemini (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                paso_json TEXT NOT NULL,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        c.execute(
            """CREATE TABLE IF NOT EXISTS analisis_estructurado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                consulta TEXT NOT NULL,
                perfil_detectado TEXT NOT NULL,
                intencion TEXT NOT NULL,
                activos_mencionados TEXT NOT NULL,
                nivel_riesgo TEXT NOT NULL,
                datos_json TEXT NOT NULL,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        c.execute(
            """CREATE TABLE IF NOT EXISTS simulaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                tipo_activo TEXT NOT NULL,
                ticker TEXT NOT NULL,
                monto_pesos REAL NOT NULL,
                precio_unitario REAL NOT NULL,
                cantidad_estimada REAL NOT NULL,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )


def guardar(chat_id, rol, contenido):
    with _conn() as c:
        c.execute(
            "INSERT INTO mensajes (chat_id, rol, contenido) VALUES (?, ?, ?)",
            (chat_id, rol, contenido),
        )


def guardar_analisis(chat_id, consulta, analisis_dict):
    with _conn() as c:
        c.execute(
            """INSERT INTO analisis_estructurado
               (chat_id, consulta, perfil_detectado, intencion, activos_mencionados, nivel_riesgo, datos_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                chat_id,
                consulta,
                analisis_dict.get("perfil_detectado", "no_especificado"),
                analisis_dict.get("intencion", "consulta_general"),
                ", ".join(analisis_dict.get("activos_mencionados", [])),
                analisis_dict.get("nivel_riesgo", "medio"),
                json.dumps(analisis_dict, ensure_ascii=False),
            ),
        )


def guardar_simulacion(chat_id, tipo_activo, ticker, monto_pesos, precio_unitario, cantidad_estimada):
    with _conn() as c:
        c.execute(
            """INSERT INTO simulaciones
               (chat_id, tipo_activo, ticker, monto_pesos, precio_unitario, cantidad_estimada)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chat_id, tipo_activo, ticker, monto_pesos, precio_unitario, cantidad_estimada),
        )


def historial(chat_id, limite=40):
    with _conn() as c:
        filas = c.execute(
            """SELECT rol, contenido FROM (
                   SELECT id, rol, contenido FROM mensajes
                   WHERE chat_id = ? ORDER BY id DESC LIMIT ?
               ) ORDER BY id ASC""",
            (chat_id, limite),
        ).fetchall()

    return [{"role": rol, "content": texto} for rol, texto in filas]


def historial_pasos(chat_id):
    with _conn() as c:
        filas = c.execute(
            """SELECT paso_json FROM pasos_gemini
               WHERE chat_id = ? ORDER BY id ASC""",
            (chat_id,),
        ).fetchall()

        if not filas:
            mensajes = c.execute(
                """SELECT rol, contenido FROM mensajes
                   WHERE chat_id = ? ORDER BY id ASC""",
                (chat_id,),
            ).fetchall()

            pasos = []

            for rol, contenido in mensajes:
                tipo = "user_input" if rol == "user" else "model_output"

                pasos.append({
                    "type": tipo,
                    "content": [
                        {"type": "text", "text": contenido}
                    ],
                })

            for paso in pasos:
                c.execute(
                    """INSERT INTO pasos_gemini
                       (chat_id, paso_json) VALUES (?, ?)""",
                    (chat_id, json.dumps(paso, ensure_ascii=False)),
                )

            return pasos

    return [json.loads(fila[0]) for fila in filas]


def guardar_pasos(chat_id, pasos):
    with _conn() as c:
        for paso in pasos:
            c.execute(
                """INSERT INTO pasos_gemini
                   (chat_id, paso_json) VALUES (?, ?)""",
                (chat_id, json.dumps(paso, ensure_ascii=False)),
            )


def borrar(chat_id):
    with _conn() as c:
        c.execute("DELETE FROM mensajes WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM pasos_gemini WHERE chat_id = ?", (chat_id,))