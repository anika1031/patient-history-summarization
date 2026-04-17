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

from pdf_utils import extract_text_from_pdf
from astra_db import (
    clean_mrn,
    store_chunks,
    vector_search,
    time_based_summary,
    medication_safety_check,
)

# ==============================
# 2️⃣ App Init
# ==============================

app = FastAPI(title="DMH Patient History Summarization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# 3️⃣ MODELS
# ==============================

class QueryRequest(BaseModel):
    mrn: str
    question: str

class TimeSummaryRequest(BaseModel):
    mrn: str
    time_range: str = "Last 6 Months"

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
    birth_date: str | None
    gender: str | None
    created_at: str | None
    updated_at: str | None

# ==============================
# 4️⃣ QUERY CLASSIFIER
# ==============================

def classify_query(question: str) -> str:
    question_lower = question.lower()

    structured_keywords = [
        "contact", "phone", "birth", "gender",
        "name", "created", "updated", "registered", "dob"
    ]

    if "mrn" in question_lower:
        if any(word in question_lower for word in structured_keywords):
            return "RDBMS"

    return "VECTOR"

# ==============================
# 5️⃣ RDBMS QUERY HANDLER
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
# 6️⃣ PDF UPLOAD API
# ==============================

@app.post("/api/upload_pdf")
def upload_pdf(mrn: str, file: UploadFile = File(...)):
    try:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Extract raw text from PDF
        extracted_text = extract_text_from_pdf(file_path)

        # Guard: join if list returned
        if isinstance(extracted_text, list):
            extracted_text = "\n".join(extracted_text)

        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Empty PDF")

        # ✅ Pass raw text — store_chunks handles chunking internally now
        store_chunks(mrn, extracted_text)

        return {
            "filename": file.filename,
            "mrn": clean_mrn(mrn),
            "status": "Stored in AstraDB"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==============================
# 7️⃣ LOAD PATIENT
# ==============================

@app.get("/api/patient/{mrn}", response_model=PatientInfoResponse)
def get_patient(mrn: str):
    db = SessionLocal()
    mrn_clean = clean_mrn(mrn)

    try:
        result = db.execute(
            text("""
                SELECT mrn, name, birth_date, gender, created_at, updated_at 
                FROM patient 
                WHERE mrn = :mrn
            """),
            {"mrn": mrn_clean}
        ).fetchone()

        db.close()

        if not result:
            raise HTTPException(status_code=404, detail="Patient not found")

        return PatientInfoResponse(
            mrn=result[0],
            name=result[1],
            birth_date=str(result[2]) if result[2] else None,
            gender=result[3],
            created_at=str(result[4]) if result[4] else None,
            updated_at=str(result[5]) if result[5] else None
        )

    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))

# ==============================
# 8️⃣ PATIENT QUERY
# ==============================

@app.post("/api/query")
def query_api(request: QueryRequest):

    mrn = clean_mrn(request.mrn)
    question = request.question
    query_type = classify_query(question)

    if query_type == "RDBMS":
        answer = handle_rdbms_query(question, mrn)
        return {"answer": answer, "query_type": "RDBMS", "sources": []}

    result = vector_search(question, mrn)

    return {
        "answer": result.get("answer", ""),
        "query_type": "VECTOR",
        "sources": result.get("sources", [])
    }

# ==============================
# 9️⃣ TIME SUMMARY
# ==============================

@app.post("/api/time_summary", response_model=TimeSummaryResponse)
def time_summary_api(request: TimeSummaryRequest):

    result = time_based_summary(request.mrn, request.time_range)

    return TimeSummaryResponse(
        summary=result["summary"],
        time_range=result["time_range"]
    )

# ==============================
# 🔟 MEDICATION SAFETY
# ==============================

@app.post("/api/medication_safety", response_model=MedSafetyResponse)
def medication_safety_api(request: MedSafetyRequest):

    result = medication_safety_check(request.mrn)

    return MedSafetyResponse(
        medications_raw=result["medications_raw"],
        interactions_raw=result["interactions_raw"],
        context_chunks_used=result["context_chunks_used"]
    )

# ==============================
# 1️⃣1️⃣ HEALTH CHECK
# ==============================

@app.get("/")
def root():
    return {"status": "✅ DMH API running", "version": "Gemini Enabled"}