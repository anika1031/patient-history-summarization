# ==============================
# 1️⃣ Imports
# ==============================

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import text
from db import SessionLocal

import os
import shutil
import requests

from pdf_utils import extract_text_from_pdf, chunk_text
from embedding_utils import generate_embedding
from astra_db import collection, store_chunks, vector_search

app = FastAPI()


# ==============================
# 2️⃣ PDF Upload API
# ==============================

@app.post("/api/upload_pdf")
def upload_pdf(mrn: str, file: UploadFile = File(...)):

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    text = extract_text_from_pdf(file_path)
    chunks = chunk_text(text)

    # Store chunks in AstraDB
    store_chunks(mrn, chunks)

    return {
        "filename": file.filename,
        "total_chunks": len(chunks),
        "status": "Stored in AstraDB"
    }

# ==============================
# 3️⃣ Request & Response Models
# ==============================

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    query_type: str


# ==============================
# 4️⃣ Query Classifier
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
        "updated",
        "registered"
    ]

    if "mrn" in question_lower:
        for word in structured_keywords:
            if word in question_lower:
                return "RDBMS"

    return "VECTOR"


# ==============================
# 5️⃣ SQL Query Handler
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
# 6️⃣ Ollama Function
# ==============================

def call_ollama(prompt: str):

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]


# ==============================
# 7️⃣ Query API
# ==============================

@app.post("/api/query", response_model=QueryResponse)
def query_api(request: QueryRequest):

    question = request.question

    query_type = classify_query(question)

    # Structured Query
    if query_type == "RDBMS":

        final_answer = handle_rdbms_query(question)

    # Vector Query
    else:

    # Extract MRN from question
        words = question.split()
        mrn = None

    for word in words:
        if "MRN" in word.upper():
            mrn = word.upper().replace("MRN","").replace("?","").strip()

    if not mrn:
        return QueryResponse(
            answer="Please include MRN in the question for document search.",
            query_type="VECTOR"
        )

    # Perform vector search
    from astra_db import vector_search

    final_answer = vector_search(question, mrn)

    return QueryResponse(
        answer=final_answer,
        query_type=query_type
    )
