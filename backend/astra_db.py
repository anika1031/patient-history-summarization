from astrapy.client import DataAPIClient
from dotenv import load_dotenv
import os
import requests

# Force load env
load_dotenv(dotenv_path=".env")

ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")

print("Endpoint:", ASTRA_DB_API_ENDPOINT)
print("Token:", ASTRA_DB_APPLICATION_TOKEN)
client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
db = client.get_database_by_api_endpoint(ASTRA_DB_API_ENDPOINT)

collection = db.get_collection("patient_chunks")

import requests

def generate_embedding(text: str):
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={
            "model": "nomic-embed-text",
            "prompt": text
        }
    )

    return response.json()["embedding"]
def store_chunks(mrn: str, chunks: list):
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)

        document = {
            "mrn": mrn,
            "chunk_index": i,
            "text": chunk,
            "$vector": embedding
        }

        collection.insert_one(document)

print(ASTRA_DB_API_ENDPOINT)
print(ASTRA_DB_APPLICATION_TOKEN)