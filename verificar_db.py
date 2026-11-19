import sqlite3

conn = sqlite3.connect("historial.db")
c = conn.cursor()

print("\n--- ÚLTIMOS ANÁLISIS ESTRUCTURADOS (PYDANTIC) ---")
for fila in c.execute("SELECT id, consulta, perfil_detectado, intencion, activos_mencionados, nivel_riesgo FROM analisis_estructurado ORDER BY id DESC LIMIT 5"):
    print(fila)

print("\n--- ÚLTIMAS SIMULACIONES DEL FLUJO GUIADO ---")
for fila in c.execute("SELECT id, tipo_activo, ticker, monto_pesos, precio_unitario, cantidad_estimada FROM simulaciones ORDER BY id DESC LIMIT 5"):
    print(fila) 