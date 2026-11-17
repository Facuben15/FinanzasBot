import os
from dotenv import load_dotenv
load_dotenv(override=True)
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

for m in client.models.list():
    nombre = m.name.replace("models/", "")
    if "flash" in nombre:
        try:
            r = client.models.generate_content(
                model=nombre, contents="Decime hola"
            )
            print("FUNCIONA:", nombre)
        except Exception as e:
            print("FALLA   :", nombre, "->", str(e)[:60])