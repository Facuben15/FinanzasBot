
import asyncio
import logging
import os

from dotenv import load_dotenv
load_dotenv(override=True)

from google import genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
import finanzas
from prompts import SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
MODEL = os.environ["GEMINI_MODEL"]
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# MENU PRINCIPAL
def obtener_menu():
    botones = [
        [KeyboardButton("📈 Consultar los mejores")],
        [KeyboardButton("🔎 Buscar acción o CEDEAR")],
        [KeyboardButton("💬 Consultar a FinanzasBot")],
    ]

    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


# MENU PARA VOLVER
def obtener_menu_volver():
    botones = [
        [KeyboardButton("⬅️ Volver al menú")]
    ]

    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


# CONVERSACION CON GEMINI
def armar_turnos(historial):
    turnos = []

    for h in historial:
        tipo = "user_input" if h["role"] == "user" else "model_output"

        turnos.append({
            "type": tipo,
            "content": [
                {
                    "type": "text",
                    "text": h["content"]
                }
            ]
        })

    return turnos



def preguntar_a_gemini(historial):
    ultimo_error = None

    for intento in range(3):
        try:
            interaccion = client.interactions.create(
                model=MODEL,
                input=armar_turnos(historial),
                system_instruction=SYSTEM_PROMPT,
                store=False,
            )

            respuesta = interaccion.output_text

            if not respuesta:
                raise ValueError("Gemini devolvió una respuesta vacía.")

            return respuesta

        except Exception as error:
            ultimo_error = error
            logging.exception(
                "Error de Gemini. Intento %s de 3",
                intento + 1
            )

            if intento < 2:
                import time
                time.sleep(3 * (intento + 1))

    raise ultimo_error



# FORMATO DE NUMEROS
def formato_numero(numero):
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# COMANDO START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["esperando_ticker"] = False

    await update.message.reply_text(
        "Hola, soy FinanzasBot.\n\n"
        "Puedo mostrarte los activos con mayor crecimiento, "
        "consultar una acción o CEDEAR específico y responder "
        "preguntas sobre finanzas.\n\n"
        "Elegí una opción del menú:",
        reply_markup=obtener_menu()
    )


# CONSULTAR LOS 5 MEJORES
async def consultar_mejores(update: Update):
    await update.message.reply_text(
        "Consultando los activos..."
    )

    try:
        activos = await asyncio.to_thread(
            finanzas.obtener_top_mejores
        )

        if not activos:
            await update.message.reply_text(
                "No se encontraron activos que cumplan los filtros.",
                reply_markup=obtener_menu_volver()
            )
            return

        texto = "📈 TOP 5 ACTIVOS CON MAYOR CRECIMIENTO\n\n"

        for i, activo in enumerate(activos, start=1):
            texto += (
                f"{i}. {activo['ticker']}\n"
                f"   Variación: +{formato_numero(activo['variacion'])}%\n"
                f"   Precio: ${formato_numero(activo['precio'])}\n"
                f"   Monto operado estimado: "
                f"${formato_numero(activo['monto_operado'])}\n\n"
            )

        texto += "Datos de la última rueda disponible."

        await update.message.reply_text(
            texto,
            reply_markup=obtener_menu_volver()
        )

    except Exception:
        logging.exception("Error consultando los mejores activos")
        await update.message.reply_text(
            "No pude consultar los activos. Probá nuevamente.",
            reply_markup=obtener_menu_volver()
        )


# BUSCAR UN ACTIVO ESPECIFICO
async def buscar_activo(update: Update, ticker):
    ticker = ticker.strip().upper()

    if "." not in ticker:
        ticker += ".BA"

    try:
        activo = await asyncio.to_thread(
            finanzas.consultar_activo,
            ticker
        )

        if activo is None:
            await update.message.reply_text(
                "No encontré datos para ese activo. Revisá el símbolo.",
                reply_markup=obtener_menu_volver()
            )
            return

        texto = (
            f"📊 CONSULTA DE {activo['ticker']}\n\n"
            f"Precio: ${formato_numero(activo['precio'])}\n"
            f"Variación: {activo['variacion']:+.2f}%\n"
            f"Cierre anterior: ${formato_numero(activo['cierre_anterior'])}\n"
            f"Apertura: ${formato_numero(activo['apertura'])}\n"
            f"Mínimo: ${formato_numero(activo['minimo'])}\n"
            f"Máximo: ${formato_numero(activo['maximo'])}\n"
            f"Volumen: {activo['volumen']:,}\n"
            f"Monto operado estimado: "
            f"${formato_numero(activo['monto_operado'])}\n\n"
            "Datos de la última rueda disponible."
        )

        await update.message.reply_text(
            texto,
            reply_markup=obtener_menu_volver()
        )

    except Exception:
        logging.exception("Error buscando activo")
        await update.message.reply_text(
            "Ocurrió un error al consultar ese activo.",
            reply_markup=obtener_menu_volver()
        )


# BORRAR HISTORIAL
async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.borrar(update.effective_chat.id)
    context.user_data["esperando_ticker"] = False

    await update.message.reply_text(
        "Conversación borrada. Empecemos de nuevo.",
        reply_markup=obtener_menu()
    )


# RECIBIR MENSAJES
async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto = update.message.text.strip()

    # VOLVER AL MENU
    if texto == "⬅️ Volver al menú":
        context.user_data["esperando_ticker"] = False

        await update.message.reply_text(
            "Volviste al menú principal. ¿Qué querés consultar?",
            reply_markup=obtener_menu()
        )
        return

    # CONSULTAR LOS MEJORES
    if texto == "📈 Consultar los mejores":
        context.user_data["esperando_ticker"] = False
        await consultar_mejores(update)
        return

    # BUSCAR ACCION O CEDEAR
    if texto == "🔎 Buscar acción o CEDEAR":
        context.user_data["esperando_ticker"] = True

        await update.message.reply_text(
            "Escribí el símbolo del activo que querés consultar.\n\n"
            "Ejemplos: GGAL.BA, YPFD.BA o AAPL.BA",
            reply_markup=obtener_menu_volver()
        )
        return

    # CONSULTAR A GEMINI
    if texto == "💬 Consultar a FinanzasBot":
        context.user_data["esperando_ticker"] = False

        await update.message.reply_text(
            "Escribime tu consulta sobre finanzas y mercados.",
            reply_markup=obtener_menu_volver()
        )
        return

    # SI ESTA BUSCANDO UN ACTIVO
    if context.user_data.get("esperando_ticker", False):
        context.user_data["esperando_ticker"] = False
        await buscar_activo(update, texto)
        return

    # CONVERSACION CON GEMINI
    chat_id = update.effective_chat.id

    db.guardar(chat_id, "user", texto)
    historial = db.historial(chat_id)

    try:
        respuesta = await asyncio.to_thread(
            preguntar_a_gemini,
            historial
        )

    except Exception:
        logging.exception("Error al llamar a Gemini")
        await update.message.reply_text(
            "Tuve un problema para responder. Probá de nuevo.",
            reply_markup=obtener_menu_volver()
        )
        return

    db.guardar(chat_id, "model", respuesta)

    await update.message.reply_text(
        respuesta,
        reply_markup=obtener_menu_volver()
    )


# INICIAR BOT
def main():
    db.init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("borrar", borrar))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            mensaje
        )
    )

    print("FinanzasBot está funcionando...")
    app.run_polling()


if __name__ == "__main__":
    main()
