import sqlite3

conexion = sqlite3.connect("historial.db")

tablas = conexion.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

print("Tablas encontradas:")
for tabla in tablas:
    print("-", tabla[0])

conexion.close()