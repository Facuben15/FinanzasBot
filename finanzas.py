
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


def consultar_activo(ticker):
    try:
        activo = yf.Ticker(ticker)

        datos = activo.history(
            period="5d",
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

        variacion = (
            (precio - cierre_anterior) / cierre_anterior
        ) * 100

        monto_operado = precio * volumen

        return {
            "ticker": ticker,
            "precio": precio,
            "cierre_anterior": cierre_anterior,
            "variacion": variacion,
            "volumen": volumen,
            "monto_operado": monto_operado,
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
    # Juntamos acciones y CEDEARs
    todos = (
        obtener_top_acciones()
        + obtener_top_cedears()
    )

    # Ordenamos de mayor a menor crecimiento
    todos.sort(
        key=lambda activo: activo["variacion"],
        reverse=True
    )

    # Devolvemos solamente los 5 mejores
    return todos[:5]