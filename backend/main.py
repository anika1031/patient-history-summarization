from fastapi import FastAPI
from pydantic import BaseModel
from backend.db import SessionLocal
from sqlalchemy import text
import requests

app = FastAPI()


# ==============================
# 1️⃣ Request & Response Models
# ==============================

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    query_type: str


# ==============================
# 2️⃣ Query Classifier
# ==============================

def classify_query(question: str):
    question_lower = question.lower()

    structured_keywords = [
        "contact",
        "phone",
        "birth",
        "gender",
        "name",
        "created",
        "created at",
        "updated at",
        "registered"
    ]

    if "mrn" in question_lower:
        for word in structured_keywords:
            if word in question_lower:
                return "RDBMS"

    return "VECTOR"


# ==============================
# 3️⃣ SQL Fetch Function
# ==============================

def handle_rdbms_query(question: str):
    db = SessionLocal()

    words = question.split()
    mrn = None

    for word in words:
        if "MRN" in word.upper():
            mrn = word.upper().replace("?", "").strip()

    if not mrn:
        db.close()
        return "MRN not found"

    question_lower = question.lower()

    # Decide which column to fetch
    if "contact" in question_lower or "phone" in question_lower:
        column = "contact"
    elif "name" in question_lower:
        column = "name"
    elif "gender" in question_lower:
        column = "gender"
    elif "birth" in question_lower or "dob" in question_lower:
        column = "birth_date"
    elif "created" in question_lower:
        column = "created_at"
    elif "updated" in question_lower:
        column = "updated_at"
    else:
        db.close()
        return "Unsupported structured query"

    query = text(f"SELECT {column} FROM patient WHERE mrn = :mrn")
    result = db.execute(query, {"mrn": mrn}).fetchone()

    db.close()

    if result and result[0]:
        return f"The {column} of {mrn} is {result[0]}"
    else:
        return f"No patient found with MRN {mrn}"
# ==============================
# 4️⃣ Ollama Call Function
# ==============================

def call_ollama(prompt: str):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "tinyllama",  # change if using another model
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]


# ==============================
# 5️⃣ Main API Endpoint
# ==============================

@app.post("/api/query", response_model=QueryResponse)
def query_api(request: QueryRequest):

    question = request.question

    query_type = classify_query(question)

    if query_type == "RDBMS":
        final_answer = handle_rdbms_query(question)
    else:
        raw_data = "Vector search not implemented yet"
        final_answer = call_ollama(
            f"Answer clearly using only the provided information:\n\n{raw_data}\n\nDo not change numbers."
    )

    return QueryResponse(
    answer=final_answer,
    query_type=query_type
)