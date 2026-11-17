
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


def guardar(chat_id, rol, contenido):
    with _conn() as c:
        c.execute(
            "INSERT INTO mensajes (chat_id, rol, contenido) VALUES (?, ?, ?)",
            (chat_id, rol, contenido),
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

        # Recuperar conversaciones anteriores si todavía
        # estaban guardadas en la tabla mensajes.
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
