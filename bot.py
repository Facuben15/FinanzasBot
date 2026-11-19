import asyncio
import json
import logging
import os
import re
import time
from typing import List, Literal

from dotenv import load_dotenv
load_dotenv(override=True)

from google import genai
from pydantic import BaseModel, Field
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


# ESQUEMA PYDANTIC PARA SALIDA ESTRUCTURADA (HITO 4)
class AnalisisConsulta(BaseModel):
    respuesta_usuario: str = Field(
        description="Respuesta clara en texto plano para enviar al usuario en Telegram"
    )
    perfil_detectado: Literal["conservador", "moderado", "agresivo", "no_especificado"] = Field(
        description="Perfil de inversor detectado en la conversación"
    )
    intencion: Literal["cotizacion", "ranking", "educacion_financiera", "cartera", "fuera_de_tema"] = Field(
        description="Categoría principal de la consulta del usuario"
    )
    activos_mencionados: List[str] = Field(
        default_factory=list,
        description="Lista de tickers mencionados (ej. ['NVDA.BA', 'GGAL.BA'])"
    )
    nivel_riesgo: Literal["bajo", "medio", "alto", "no_aplica"] = Field(
        description="Nivel de riesgo asociado a la consulta o activos tratados"
    )


# MENUS DE TELEGRAM
def obtener_menu():
    botones = [
        [KeyboardButton("📈 Consultar los mejores")],
        [KeyboardButton("🔎 Buscar acción o CEDEAR")],
        [KeyboardButton("🧮 Simular inversión")],
        [KeyboardButton("💬 Consultar a FinanzasBot")],
    ]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


def obtener_menu_volver():
    botones = [[KeyboardButton("⬅️ Volver al menú")]]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


def obtener_menu_tipo_activo():
    botones = [
        [KeyboardButton("Acción Argentina"), KeyboardButton("CEDEAR")],
        [KeyboardButton("❌ Cancelar simulación")],
    ]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


def obtener_menu_cancelar_flujo():
    botones = [[KeyboardButton("❌ Cancelar simulación")]]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


def obtener_menu_confirmar_flujo():
    botones = [
        [KeyboardButton("✅ Confirmar simulación"), KeyboardButton("❌ Cancelar simulación")]
    ]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)


# CONVERSACION CON GEMINI + SALIDA ESTRUCTURADA
def armar_turnos(historial):
    turnos = []
    for h in historial:
        tipo = "user_input" if h["role"] == "user" else "model_output"
        turnos.append({
            "type": tipo,
            "content": [{"type": "text", "text": h["content"]}]
        })
    return turnos


def _limpiar_json(texto):
    texto = texto.strip()
    bloque = re.search(r"\{.*\}", texto, re.DOTALL)
    return bloque.group(0) if bloque else texto


def preguntar_a_gemini_estructurado(historial, ultima_consulta=""):
    ultimo_error = None
    contexto_mercado = finanzas.obtener_contexto_mercado(ultima_consulta)

    instruccion_json = (
        "\n\n# SALIDA ESTRUCTURADA OBLIGATORIA\n"
        "Debes responder ÚNICAMENTE con un objeto JSON válido (sin bloques markdown ```json) "
        "que cumpla exactamente con estas claves:\n"
        "{\n"
        '  "respuesta_usuario": "texto plano con tu respuesta siguiendo las reglas de formato",\n'
        '  "perfil_detectado": "conservador" | "moderado" | "agresivo" | "no_especificado",\n'
        '  "intencion": "cotizacion" | "ranking" | "educacion_financiera" | "cartera" | "fuera_de_tema",\n'
        '  "activos_mencionados": ["TICKER.BA"],\n'
        '  "nivel_riesgo": "bajo" | "medio" | "alto" | "no_aplica"\n'
        "}"
    )

    instruccion_con_datos = f"{SYSTEM_PROMPT}\n\n{contexto_mercado}{instruccion_json}"

    for intento in range(3):
        try:
            interaccion = client.interactions.create(
                model=MODEL,
                input=armar_turnos(historial),
                system_instruction=instruccion_con_datos,
                store=False,
            )

            texto_crudo = interaccion.output_text
            if not texto_crudo:
                raise ValueError("Gemini devolvió una respuesta vacía.")

            json_limpio = _limpiar_json(texto_crudo)
            objeto_validado = AnalisisConsulta.model_validate_json(json_limpio)

            print("\n=== [SALIDA ESTRUCTURADA VALIDADA CON PYDANTIC] ===")
            print(json.dumps(objeto_validado.model_dump(), indent=2, ensure_ascii=False))
            print("===================================================\n")

            return objeto_validado

        except Exception as error:
            ultimo_error = error
            logging.exception("Error de Gemini o validación Pydantic. Intento %s de 3", intento + 1)
            if intento < 2:
                time.sleep(2 * (intento + 1))

    raise ultimo_error


def preguntar_a_gemini(historial, ultima_consulta=""):
    resultado = preguntar_a_gemini_estructurado(historial, ultima_consulta)
    return resultado.respuesta_usuario


# FORMATO DE NUMEROS
def formato_numero(numero):
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# COMANDO START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Hola, soy FinanzasBot.\n\n"
        "Puedo mostrarte los activos con mayor crecimiento, "
        "consultar una acción o CEDEAR específico, simular una inversión "
        "paso a paso y responder preguntas sobre finanzas.\n\n"
        "Elegí una opción del menú:",
        reply_markup=obtener_menu()
    )


# CONSULTAR LOS 5 MEJORES
async def consultar_mejores(update: Update):
    await update.message.reply_text("Consultando los activos...")

    try:
        activos = await asyncio.to_thread(finanzas.obtener_top_mejores)

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
                f"   Monto operado estimado: ${formato_numero(activo['monto_operado'])}\n\n"
            )
        texto += "Datos de la última rueda disponible."

        await update.message.reply_text(texto, reply_markup=obtener_menu_volver())

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
        activo = await asyncio.to_thread(finanzas.consultar_activo, ticker)

        if activo is None:
            await update.message.reply_text(
                "No encontré datos para ese activo. Revisá el símbolo.",
                reply_markup=obtener_menu_volver()
            )
            return

        texto = (
            f"📊 CONSULTA DE {activo['ticker']}\n\n"
            f"Precio: ${formato_numero(activo['precio'])}\n"
            f"Variación diaria: {activo['variacion']:+.2f}%\n"
            f"Variación semanal: {activo.get('variacion_semanal', 0.0):+.2f}%\n"
            f"Cierre anterior: ${formato_numero(activo['cierre_anterior'])}\n"
            f"Apertura: ${formato_numero(activo['apertura'])}\n"
            f"Mínimo: ${formato_numero(activo['minimo'])}\n"
            f"Máximo: ${formato_numero(activo['maximo'])}\n"
            f"Volumen: {activo['volumen']:,}\n"
            f"Monto operado estimado: ${formato_numero(activo['monto_operado'])}\n\n"
            "Datos de la última rueda disponible."
        )

        await update.message.reply_text(texto, reply_markup=obtener_menu_volver())

    except Exception:
        logging.exception("Error buscando activo")
        await update.message.reply_text(
            "Ocurrió un error al consultar ese activo.",
            reply_markup=obtener_menu_volver()
        )


# FLUJO GUIADO: SIMULADOR DE INVERSION (HITO 4)
async def manejar_flujo_simulacion(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    paso = context.user_data.get("flujo_paso")

    # Cancelación en cualquier punto del flujo
    if texto == "❌ Cancelar simulación" or texto.lower() == "cancelar":
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Simulación cancelada. Volviste al menú principal.",
            reply_markup=obtener_menu()
        )
        return

    # PASO 1: Validar tipo de activo
    if paso == "tipo":
        if texto not in ("Acción Argentina", "CEDEAR"):
            await update.message.reply_text(
                "⚠️ Opción inválida. Por favor, elegí 'Acción Argentina' o 'CEDEAR' usando los botones, o tocá Cancelar.",
                reply_markup=obtener_menu_tipo_activo()
            )
            return

        context.user_data["sim_tipo"] = texto
        context.user_data["flujo_paso"] = "ticker"
        ejemplos = "GGAL, YPFD, PAMP" if texto == "Acción Argentina" else "NVDA, AAPL, MELI"

        await update.message.reply_text(
            f"Paso 2 de 4: Elegiste {texto}.\n"
            f"Escribí el símbolo (ticker) del activo que querés simular (Ejemplos: {ejemplos}):",
            reply_markup=obtener_menu_cancelar_flujo()
        )
        return

    # PASO 2: Validar que el ticker sea válido y exista en Yahoo Finance
    if paso == "ticker":
        ticker = texto.strip().upper()
        if not re.match(r"^[A-Z0-9]{2,6}(\.BA)?$", ticker):
            await update.message.reply_text(
                "⚠️ Formato de símbolo inválido. Ingresá solo las letras del ticker (ej. GGAL o NVDA):",
                reply_markup=obtener_menu_cancelar_flujo()
            )
            return

        if "." not in ticker:
            ticker += ".BA"

        await update.message.reply_text(f"Verificando cotización de {ticker}...")
        datos = await asyncio.to_thread(finanzas.consultar_activo, ticker)

        if datos is None:
            await update.message.reply_text(
                f"⚠️ No se encontró el activo '{ticker}' en el mercado. Ingresá un símbolo válido (ej. AAPL, MELI, YPFD):",
                reply_markup=obtener_menu_cancelar_flujo()
            )
            return

        context.user_data["sim_ticker"] = ticker
        context.user_data["sim_precio"] = datos["precio"]
        context.user_data["flujo_paso"] = "monto"

        await update.message.reply_text(
            f"Paso 3 de 4: {ticker} cotiza a ${formato_numero(datos['precio'])}.\n"
            "Ingresá el monto en pesos argentinos que querés invertir (mínimo $1.000):",
            reply_markup=obtener_menu_cancelar_flujo()
        )
        return

    # PASO 3: Validar monto numérico positivo
    if paso == "monto":
        texto_limpio = texto.replace("$", "").replace(".", "").replace(",", ".").strip()
        try:
            monto = float(texto_limpio)
        except ValueError:
            await update.message.reply_text(
                "⚠️ Dato inválido: debés ingresar un número válido sin letras (ejemplo: 250000). Intentá de nuevo:",
                reply_markup=obtener_menu_cancelar_flujo()
            )
            return

        if monto < 1000:
            await update.message.reply_text(
                "⚠️ El monto mínimo para simular es de $1.000. Ingresá un monto mayor:",
                reply_markup=obtener_menu_cancelar_flujo()
            )
            return

        precio = context.user_data["sim_precio"]
        ticker = context.user_data["sim_ticker"]
        tipo = context.user_data["sim_tipo"]
        comision = monto * 0.005
        monto_neto = monto - comision
        cantidad = monto_neto / precio

        context.user_data["sim_monto"] = monto
        context.user_data["sim_cantidad"] = cantidad
        context.user_data["flujo_paso"] = "confirmar"

        resumen = (
            "📋 Paso 4 de 4: RESUMEN DE SIMULACIÓN\n\n"
            f"• Instrumento: {tipo}\n"
            f"• Activo: {ticker}\n"
            f"• Precio actual: ${formato_numero(precio)}\n"
            f"• Capital a invertir: ${formato_numero(monto)}\n"
            f"• Comisión estimada (0,5%): ${formato_numero(comision)}\n"
            f"• Cantidad estimada a comprar: {formato_numero(cantidad)} unidades\n\n"
            "¿Confirmás el registro de esta simulación?"
        )
        await update.message.reply_text(resumen, reply_markup=obtener_menu_confirmar_flujo())
        return

    # PASO 4: Confirmación final
    if paso == "confirmar":
        if texto == "✅ Confirmar simulación":
            db.guardar_simulacion(
                update.effective_chat.id,
                context.user_data["sim_tipo"],
                context.user_data["sim_ticker"],
                context.user_data["sim_monto"],
                context.user_data["sim_precio"],
                context.user_data["sim_cantidad"],
            )
            print(
                f"\n[SIMULACIÓN GUARDADA EN DB] Chat: {update.effective_chat.id} | "
                f"Activo: {context.user_data['sim_ticker']} | "
                f"Monto: ${context.user_data['sim_monto']:,.2f}\n"
            )
            context.user_data.clear()
            await update.message.reply_text(
                "✅ ¡Simulación confirmada y guardada con éxito en la base de datos!\n"
                "Recordá que este cálculo es orientativo y no constituye una orden real de mercado.",
                reply_markup=obtener_menu()
            )
            return

        await update.message.reply_text(
            "Por favor, elegí '✅ Confirmar simulación' o '❌ Cancelar simulación'.",
            reply_markup=obtener_menu_confirmar_flujo()
        )


# BORRAR HISTORIAL
async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.borrar(update.effective_chat.id)
    context.user_data.clear()

    await update.message.reply_text(
        "Conversación borrada. Empecemos de nuevo.",
        reply_markup=obtener_menu()
    )


# RECIBIR MENSAJES
async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto = update.message.text.strip()

    # Si el usuario está dentro del flujo guiado de simulación
    if context.user_data.get("flujo_paso"):
        await manejar_flujo_simulacion(update, context, texto)
        return

    # VOLVER AL MENU
    if texto == "⬅️ Volver al menú":
        context.user_data.clear()
        await update.message.reply_text(
            "Volviste al menú principal. ¿Qué querés consultar?",
            reply_markup=obtener_menu()
        )
        return

    # INICIAR FLUJO GUIADO
    if texto == "🧮 Simular inversión":
        context.user_data.clear()
        context.user_data["flujo_paso"] = "tipo"
        await update.message.reply_text(
            "🧮 SIMULADOR DE INVERSIÓN (Paso 1 de 4)\n\n"
            "Elegí qué tipo de instrumento querés simular:",
            reply_markup=obtener_menu_tipo_activo()
        )
        return

    # CONSULTAR LOS MEJORES
    if texto == "📈 Consultar los mejores":
        context.user_data.clear()
        await consultar_mejores(update)
        return

    # BUSCAR ACCION O CEDEAR
    if texto == "🔎 Buscar acción o CEDEAR":
        context.user_data.clear()
        context.user_data["esperando_ticker"] = True
        await update.message.reply_text(
            "Escribí el símbolo del activo que querés consultar.\n\n"
            "Ejemplos: GGAL.BA, YPFD.BA o AAPL.BA",
            reply_markup=obtener_menu_volver()
        )
        return

    # CONSULTAR A GEMINI
    if texto == "💬 Consultar a FinanzasBot":
        context.user_data.clear()
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

    # CONVERSACION CON GEMINI + SALIDA ESTRUCTURADA GUARDADA EN DB
    chat_id = update.effective_chat.id
    db.guardar(chat_id, "user", texto)
    historial = db.historial(chat_id)

    try:
        analisis = await asyncio.to_thread(
            preguntar_a_gemini_estructurado,
            historial,
            texto
        )
        respuesta = analisis.respuesta_usuario
        db.guardar_analisis(chat_id, texto, analisis.model_dump())

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))

    print("FinanzasBot está funcionando...")
    app.run_polling()


if __name__ == "__main__":
    main()