import os
from dotenv import load_dotenv
load_dotenv(override=True)
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
r = client.models.generate_content(
    model=os.environ["GEMINI_MODEL"],
    contents="Decime hola"
)
print(r.text)