import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "tinyllama",
        "prompt": "Explain what a discharge summary is in simple terms.",
        "stream": False
    }
)

print(response.json()["response"])
