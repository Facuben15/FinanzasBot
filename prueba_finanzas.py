import finanzas

print("CONSULTA DE ACCIONES")

acciones = finanzas.obtener_top_acciones()

for activo in acciones:
    print(
        activo["ticker"],
        activo["variacion"],
        activo["monto_operado"]
    )


print("\nCONSULTA DE CEDEARS")

cedears = finanzas.obtener_top_cedears()

for activo in cedears:
    print(
        activo["ticker"],
        activo["variacion"],
        activo["monto_operado"]
    )