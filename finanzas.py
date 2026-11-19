import re
import yfinance as yf


# Acciones argentinas que vamos a consultar
ACCIONES = [
    "GGAL.BA",
    "YPFD.BA",
    "BMA.BA",
    "PAMP.BA",
    "TXAR.BA",
    "TGSU2.BA",
    "COME.BA",
    "ALUA.BA",
]

# CEDEARs que vamos a consultar
CEDEARS = [
    "AAPL.BA",
    "TSLA.BA",
    "MELI.BA",
    "AMZN.BA",
    "MSFT.BA",
    "NVDA.BA",
    "GOOGL.BA",
    "META.BA",
]


def _calcular_periodo(datos_periodo, precio_actual):
    if len(datos_periodo) == 0:
        return 0.0, 0, 0.0
    primero = float(datos_periodo.iloc[0]["Close"])
    variacion = ((precio_actual - primero) / primero) * 100 if primero > 0 else 0.0
    volumen = int(datos_periodo["Volume"].sum())
    monto = float((datos_periodo["Close"] * datos_periodo["Volume"]).sum())
    return variacion, volumen, monto


def consultar_activo(ticker):
    try:
        activo = yf.Ticker(ticker)

        # Pedimos 3 meses de una sola vez para tener día, semana, mes y 3 meses
        datos = activo.history(
            period="3mo",
            interval="1d"
        )

        if len(datos) < 2:
            return None

        ultimo = datos.iloc[-1]
        anterior = datos.iloc[-2]

        precio = float(ultimo["Close"])
        cierre_anterior = float(anterior["Close"])
        volumen = int(ultimo["Volume"])

        if cierre_anterior <= 0:
            return None

        variacion = ((precio - cierre_anterior) / cierre_anterior) * 100
        monto_operado = precio * volumen

        # Última semana (~5 ruedas), último mes (~21 ruedas) y últimos 3 meses (todo)
        var_sem, vol_sem, monto_sem = _calcular_periodo(datos.tail(5), precio)
        var_mes, vol_mes, monto_mes = _calcular_periodo(datos.tail(21), precio)
        var_3m, vol_3m, monto_3m = _calcular_periodo(datos, precio)

        return {
            "ticker": ticker,
            "precio": precio,
            "cierre_anterior": cierre_anterior,
            "variacion": variacion,
            "volumen": volumen,
            "monto_operado": monto_operado,
            "variacion_semanal": var_sem,
            "volumen_semanal": vol_sem,
            "monto_semanal": monto_sem,
            "variacion_mensual": var_mes,
            "volumen_mensual": vol_mes,
            "monto_mensual": monto_mes,
            "variacion_3m": var_3m,
            "volumen_3m": vol_3m,
            "monto_3m": monto_3m,
            "apertura": float(ultimo["Open"]),
            "minimo": float(ultimo["Low"]),
            "maximo": float(ultimo["High"])
        }

    except Exception as error:
        print(f"Error consultando {ticker}: {error}")
        return None


def obtener_top_activos(lista, monto_minimo):
    resultados = []

    for ticker in lista:
        datos = consultar_activo(ticker)

        if datos is None:
            continue

        if datos["variacion"] > 0 and datos["monto_operado"] > monto_minimo:
            resultados.append(datos)

    resultados.sort(
        key=lambda activo: activo["variacion"],
        reverse=True
    )

    return resultados[:10]


def obtener_top_acciones():
    return obtener_top_activos(ACCIONES, 50000)


def obtener_top_cedears():
    return obtener_top_activos(CEDEARS, 1000000)


def obtener_top_mejores():
    todos = (
        obtener_top_acciones()
        + obtener_top_cedears()
    )

    todos.sort(
        key=lambda activo: activo["variacion"],
        reverse=True
    )

    return todos[:5]


def _formatear_linea(d):
    return (
        f"- {d['ticker']}: Precio ${d['precio']:,.2f} | "
        f"Hoy: {d['variacion']:+.2f}% (Monto ${d['monto_operado']:,.0f}) | "
        f"Semana: {d['variacion_semanal']:+.2f}% (Monto ${d['monto_semanal']:,.0f}) | "
        f"Mes: {d['variacion_mensual']:+.2f}% (Monto ${d['monto_mensual']:,.0f}) | "
        f"3 Meses: {d['variacion_3m']:+.2f}% (Monto ${d['monto_3m']:,.0f})"
    )


def obtener_contexto_mercado(consulta_usuario=""):
    """Obtiene los datos en vivo de Yahoo Finance (día, semana, mes y 3 meses) para Gemini."""
    lineas = ["[DATOS DE MERCADO EN TIEMPO REAL - YAHOO FINANCE (BYMA)]"]

    datos_cedears = [d for t in CEDEARS if (d := consultar_activo(t))]
    datos_acciones = [d for t in ACCIONES if (d := consultar_activo(t))]

    if datos_cedears:
        datos_cedears.sort(key=lambda x: x["monto_semanal"], reverse=True)
        lineas.append("\nCEDEARs:")
        for d in datos_cedears:
            lineas.append(_formatear_linea(d))

    if datos_acciones:
        datos_acciones.sort(key=lambda x: x["monto_semanal"], reverse=True)
        lineas.append("\nAcciones Argentinas:")
        for d in datos_acciones:
            lineas.append(_formatear_linea(d))

    palabras = re.findall(r"\b[A-Za-z]{2,6}(?:\.BA)?\b", consulta_usuario.upper())
    conocidos = set(CEDEARS + ACCIONES)
    ignorar = {"QUE", "LOS", "LAS", "DEL", "MAS", "SON", "CON", "POR", "UNA", "COMO", "PARA", "HOLA", "SEMANA", "ULTIMA", "ULTIMO", "MES", "MESES", "TRES", "TOP", "CEDEAR", "CEDEARS"}
    for p in palabras:
        posible = p if "." in p else f"{p}.BA"
        if posible not in conocidos and p not in ignorar:
            extra = consultar_activo(posible)
            if extra:
                conocidos.add(posible)
                lineas.append(f"\nActivo adicional consultado:\n{_formatear_linea(extra)}")

    return "\n".join(lineas)