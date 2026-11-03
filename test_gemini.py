import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model='gemini-3.8-flash', # Ganti dengan model terbaru
    contents="Jawab singkat: Halo, apakah AI berfungsi?"
)
print(response.text)