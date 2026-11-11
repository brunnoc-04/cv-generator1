import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print("Chave carregada:", f"{key[:6]}..." if key else "NÃO ENCONTRADA")

client = genai.Client(api_key=key)
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name)
