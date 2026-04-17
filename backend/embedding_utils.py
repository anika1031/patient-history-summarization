
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-mpnet-base-v2")  # ✅ 768 dimensions

def generate_embedding(text: str):
    return model.encode(text).tolist()