# ==============================
# 1️⃣ Imports
# ==============================

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from db import SessionLocal

import os
import shutil


from pdf_utils import extract_text_from_pdf, chunk_text
from embedding_utils import generate_embedding
from astra_db import (
    collection,
    clean_mrn,
    store_chunks,
    vector_search,
    time_based_summary,
    medication_safety_check,
)

app = FastAPI(title="DMH Patient History Summarization API")
# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# REQUEST / RESPONSE MODELS
# ==============================

class QueryRequest(BaseModel):
    mrn: str
    question: str

class QueryResponse(BaseModel):
    answer: str
    query_type: str
    sources: list = []

class TimeSummaryRequest(BaseModel):
    mrn: str
    time_range: str = "Last 6 Months"   # "Last 1 Month" | "Last 3 Months" | "Last 6 Months" | "Last 1 Year"

class TimeSummaryResponse(BaseModel):
    summary: str
    time_range: str

class MedSafetyRequest(BaseModel):
    mrn: str

class MedSafetyResponse(BaseModel):
    medications_raw: str
    interactions_raw: str
    context_chunks_used: int

class PatientInfoResponse(BaseModel):
    mrn: str
    name: str
    age: int | None
    gender: str | None
    last_encounter: str | None

# ==============================
# QUERY CLASSIFIER
# ==============================

def classify_query(question: str) -> str:
    question_lower = question.lower()
    structured_keywords = [
        "contact", "phone", "birth", "gender",
        "name", "created", "updated", "registered", "age"
    ]
    if "mrn" in question_lower:
        for word in structured_keywords:
            if word in question_lower:
                return "RDBMS"
    return "VECTOR"


# ==============================
# SQL QUERY HANDLER
# ==============================

def handle_rdbms_query(question: str, mrn: str) -> str:
    db = SessionLocal()
    mrn = clean_mrn(mrn)
    question_lower = question.lower()

    column_map = {
        "contact": ["contact", "phone"],
        "name": ["name"],
        "gender": ["gender"],
        "birth_date": ["birth", "dob"],
        "created_at": ["created"],
        "updated_at": ["updated"],
    }

    column = None
    for col, keywords in column_map.items():
        if any(kw in question_lower for kw in keywords):
            column = col
            break

    if not column:
        db.close()
        return "Unsupported structured query."

    try:
        query = text(f"SELECT {column} FROM patient WHERE mrn = :mrn")
        result = db.execute(query, {"mrn": mrn}).fetchone()
        db.close()
        if result and result[0]:
            return f"The {column.replace('_', ' ')} of MRN {mrn} is: {result[0]}"
        return f"No patient found with MRN {mrn}."
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))



# ==============================
# 2️⃣ PDF Upload API
# ==============================

@app.post("/api/upload_pdf")
def upload_pdf(mrn: str, file: UploadFile = File(...)):
    """Upload a discharge summary PDF and store chunks in AstraDB."""
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
        "mrn": clean_mrn(mrn),
        "total_chunks": len(chunks),
        "status": "Stored in AstraDB"
    }

# ==============================
# 2️⃣ LOAD PATIENT (structured DB)
# ==============================

@app.get("/api/patient/{mrn}", response_model=PatientInfoResponse)
def get_patient(mrn: str):
    """Load patient demographic info from SQL DB."""
    db = SessionLocal()
    mrn_clean = clean_mrn(mrn)

    try:
        result = db.execute(
            text("SELECT mrn, name, age, gender, last_encounter FROM patient WHERE mrn = :mrn"),
            {"mrn": mrn_clean}
        ).fetchone()
        db.close()

        if not result:
            raise HTTPException(status_code=404, detail=f"Patient MRN {mrn_clean} not found.")

        return PatientInfoResponse(
            mrn=result[0],
            name=result[1],
            age=result[2],
            gender=result[3],
            last_encounter=str(result[4]) if result[4] else None
        )
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==============================
# 3️⃣ PATIENT QUERY (Tab 1)
# ==============================

@app.post("/api/query", response_model=QueryResponse)
def query_api(request: QueryRequest):
    """
    Hybrid query: routes to RDBMS for structured fields
    or Vector DB for clinical questions.
    """
    question = request.question
    mrn = clean_mrn(request.mrn)
    query_type = classify_query(question)

    if query_type == "RDBMS":
        answer = handle_rdbms_query(question, mrn)
        return QueryResponse(answer=answer, query_type="RDBMS", sources=[])

    # VECTOR search
    result = vector_search(question, mrn)
    return QueryResponse(
        answer=result["answer"],
        query_type="VECTOR",
        sources=result.get("sources", [])
    )


# ==============================
# 4️⃣ TIME-BASED SUMMARY (Tab 2)
# ==============================

@app.post("/api/time_summary", response_model=TimeSummaryResponse)
def time_summary_api(request: TimeSummaryRequest):
    """
    Generate a chronological summary of patient history
    for a selected time range.
    Supported time_range values:
      "Last 1 Month" | "Last 3 Months" | "Last 6 Months" | "Last 1 Year"
    """
    mrn = clean_mrn(request.mrn)
    result = time_based_summary(mrn, request.time_range)
    return TimeSummaryResponse(
        summary=result["summary"],
        time_range=result["time_range"]
    )


# ==============================
# 5️⃣ MEDICATION SAFETY (Tab 3)
# ==============================

@app.post("/api/medication_safety", response_model=MedSafetyResponse)
def medication_safety_api(request: MedSafetyRequest):
    """
    Extract all medications from patient record and
    check for drug-drug interactions.
    """
    mrn = clean_mrn(request.mrn)
    result = medication_safety_check(mrn)
    return MedSafetyResponse(
        medications_raw=result["medications_raw"],
        interactions_raw=result["interactions_raw"],
        context_chunks_used=result["context_chunks_used"]
    )


# ==============================
# HEALTH CHECK
# ==============================

@app.get("/")
def root():
    return {"status": "✅ DMH API running", "version": "1.0"}

@app.post("/ask")
def ask_question(request: dict):

    question = request["question"]
    mrn = request["mrn"]

    answer = vector_search(question, mrn)

    return {
        "answer": answer,
        "query_type": "VECTOR"
    }