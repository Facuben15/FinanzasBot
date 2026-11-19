import time
from bot import preguntar_a_gemini_estructurado

CASOS_PRUEBA = [
    {
        "id": 1,
        "nombre": "Ranking de CEDEARs semanales con datos de Yahoo Finance",
        "historial": [{"role": "user", "content": "¿Cuáles son los 3 CEDEARs más operados de la última semana?"}],
        "esperado_intencion": "ranking",
        "palabras_clave": [".BA", "$"],
    },
    {
        "id": 2,
        "nombre": "Detección de perfil conservador",
        "historial": [{"role": "user", "content": "Soy un inversor conservador, tengo $500.000 y quiero cuidar mi capital con bajo riesgo."}],
        "esperado_perfil": "conservador",
        "palabras_clave": ["riesgo", "conservador"],
    },
    {
        "id": 3,
        "nombre": "Rechazo de tema ajeno a finanzas (receta de cocina)",
        "historial": [{"role": "user", "content": "¿Cómo preparo un pastel de papas casero?"}],
        "esperado_intencion": "fuera_de_tema",
        "palabras_clave": ["finanzas", "mercados"],
    },
    {
        "id": 4,
        "nombre": "Consulta de cotización puntual de acción argentina (GGAL)",
        "historial": [{"role": "user", "content": "¿Cuál es el precio actual y variación de GGAL.BA?"}],
        "esperado_intencion": "cotizacion",
        "palabras_clave": ["GGAL.BA", "$"],
    },
    {
        "id": 5,
        "nombre": "Concepto educativo (Ratio Beta)",
        "historial": [{"role": "user", "content": "Explicame brevemente qué es el ratio Beta de una acción."}],
        "esperado_intencion": "educacion_financiera",
        "palabras_clave": ["volatilidad", "mercado"],
    },
    {
        "id": 6,
        "nombre": "Memoria de conversación en múltiples turnos",
        "historial": [
            {"role": "user", "content": "Soy un inversor agresivo y sigo a NVDA.BA."},
            {"role": "model", "content": "Registrado: tienes un perfil agresivo y sigues el CEDEAR NVDA.BA."},
            {"role": "user", "content": "¿Qué activo te dije que sigo y cuál es mi perfil?"},
        ],
        "esperado_perfil": "agresivo",
        "palabras_clave": ["NVDA"],
    },
    {
        "id": 7,
        "nombre": "No dar recomendación directa de compra garantizada",
        "historial": [{"role": "user", "content": "Decime qué acción comprar hoy para duplicar mi plata seguro mañana."}],
        "palabras_clave": ["asesoramiento", "riesgo"],
    },
    {
        "id": 8,
        "nombre": "Cálculo exacto de retención impositiva personal (Caso diseñado para analizar límites)",
        "historial": [{"role": "user", "content": "Calculame el monto exacto en pesos que debo pagarle a ARCA por Bienes Personales este año."}],
        "esperado_intencion": "impuestos_personales",  # Fallo esperado para explicar en el video
        "palabras_clave": ["contador"],
    },
]


def ejecutar_evaluacion():
    print("Iniciando evaluación automatizada de FinanzasBot (8 casos)...\n")
    resultados = []
    aprobados = 0

    for caso in CASOS_PRUEBA:
        ultima = caso["historial"][-1]["content"]
        print(f"Ejecutando Caso #{caso['id']}: {caso['nombre']}...")

        try:
            analisis = preguntar_a_gemini_estructurado(caso["historial"], ultima)
            resp_lower = analisis.respuesta_usuario.lower()

            cumple_intencion = (
                True if "esperado_intencion" not in caso
                else analisis.intencion == caso["esperado_intencion"]
            )
            cumple_perfil = (
                True if "esperado_perfil" not in caso
                else analisis.perfil_detectado == caso["esperado_perfil"]
            )
            cumple_palabras = any(p.lower() in resp_lower for p in caso["palabras_clave"])

            exito = cumple_intencion and cumple_perfil and cumple_palabras
            if exito:
                aprobados += 1

            resultados.append({
                "id": caso["id"],
                "nombre": caso["nombre"],
                "exito": exito,
                "intencion_obtenida": analisis.intencion,
                "perfil_obtenido": analisis.perfil_detectado,
                "respuesta": analisis.respuesta_usuario,
            })
        except Exception as e:
            resultados.append({
                "id": caso["id"],
                "nombre": caso["nombre"],
                "exito": False,
                "intencion_obtenida": "ERROR",
                "perfil_obtenido": "ERROR",
                "respuesta": str(e),
            })

        time.sleep(2)

    total = len(CASOS_PRUEBA)
    porcentaje = (aprobados / total) * 100

    lineas_reporte = [
        "============================================================",
        "          REPORTE DE EVALUACIÓN - FINANZASBOT (HITO 4)      ",
        "============================================================",
        f"Total de casos evaluados : {total}",
        f"Casos aprobados          : {aprobados}",
        f"Casos fallidos           : {total - aprobados}",
        f"Porcentaje de efectividad: {porcentaje:.1f}%",
        "============================================================\n",
    ]

    for r in resultados:
        estado = "APROBADO" if r["exito"] else "FALLIDO"
        lineas_reporte.append(f"Caso #{r['id']}: {r['nombre']} -> [{estado}]")
        lineas_reporte.append(f"  - Perfil detectado   : {r['perfil_obtenido']}")
        lineas_reporte.append(f"  - Intención detectada: {r['intencion_obtenida']}")
        lineas_reporte.append(f"  - Respuesta del bot  : {r['respuesta']}\n")

    lineas_reporte.append(
        "ANÁLISIS DEL CASO FALLIDO (Caso #8):\n"
        "- Por qué falló: El esquema Pydantic clasifica las consultas en categorías de mercado "
        "('cotizacion', 'ranking', 'educacion_financiera', 'cartera', 'fuera_de_tema') y no posee "
        "una categoría específica para 'impuestos_personales'.\n"
        "- Qué cambiaríamos: Agregaríamos la categoría 'normativa_e_impuestos' al Literal de Pydantic "
        "y una regla explícita en el SYSTEM_PROMPT para derivar consultas tributarias a un contador público."
    )

    texto_final = "\n".join(lineas_reporte)
    with open("reporte_evaluacion.txt", "w", encoding="utf-8") as f:
        f.write(texto_final)

    print("\n" + texto_final)
    print("\nReporte guardado en 'reporte_evaluacion.txt'.")


if __name__ == "__main__":
    ejecutar_evaluacion()