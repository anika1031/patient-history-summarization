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
import requests as http_requests

from pdf_utils import extract_text_from_pdf
from astra_db import (
    clean_mrn,
    store_chunks,
    vector_search,
    time_based_summary,
    medication_safety_check,
)
from dotenv import load_dotenv
load_dotenv()

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
# 3️⃣ LiteLLM Proxy Config
# ==============================

LITELLM_API_KEY  = "sk-hSrIM4Ys1zkAWQVvfplHgw"
LITELLM_BASE_URL ="http://13.234.214.173:4000"
LITELLM_MODEL    = "nova-lite"

LITELLM_HEADERS = {
    "Authorization": f"Bearer {LITELLM_API_KEY}",
    "Content-Type":  "application/json",
}

print(f"🚀 LiteLLM Proxy  : {LITELLM_BASE_URL}")
print(f"🤖 Model          : {LITELLM_MODEL}")
print(f"🔑 Key prefix     : {LITELLM_API_KEY[:8]}...")

# ==============================
# 4️⃣ Clinical System Prompt
# ==============================

CLINICAL_SYSTEM_PROMPT = """You are a clinical AI assistant for "DMH – Patient History Summarization System".

You analyze patient medical records retrieved from a vector database.

CORE RULES:
- Answer ONLY based on the provided context — never invent or assume information
- If something is not present in the records, state: "Not found in records"
- Do NOT include KEY FINDINGS / RISK FLAGS / RECOMMENDATIONS unless the question explicitly asks for them
- Answer ONLY what is asked — do not add unrequested sections

COMPLETENESS RULES (critical):
- REPRODUCE the full relevant content from the records — do NOT summarize, shorten, or paraphrase unless the question asks for a summary
- If a section in the records directly answers the question, extract and present it IN FULL — word for word if needed
- Never stop mid-sentence or mid-paragraph — always complete every sentence and every point
- If multiple chunks contain relevant information about the same topic, combine them into one complete answer
- Do not omit any detail that is part of the answer — partial answers are incorrect answers

RESPONSE FORMAT:
- For narrative sections (e.g. course in hospital, examination findings), return the full text as a clean paragraph
- Use bullet points only when the answer is a list of distinct items (e.g. medications, investigations)
- Do not truncate with "..." or trail off — always write the complete answer"""


# ==============================
# 5️⃣ Context Cleaner  ← FIX 4
# ==============================

def clean_context(text: str) -> str:
    """
    Normalize raw Astra context before sending to model.
    Removes triple blank lines and stray space-before-period artefacts.
    """
    return (
        text.replace("\n\n\n", "\n\n")
            .replace(" .", ".")
            .strip()
    )


# ==============================
# 6️⃣ LiteLLM Caller  ← FIX 2 + FIX 3
# ==============================

def call_nova(user_message: str, temperature: float = 0.1) -> str:
    """
    Call Nova Lite via LiteLLM proxy using OpenAI-compatible
    /chat/completions endpoint.
    """
    payload = {
        "model":       LITELLM_MODEL,
        "messages": [
            {"role": "system", "content": CLINICAL_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        "max_tokens":  3000,   # FIX 2 — increased from 2048
        "temperature": temperature,
        "stop":        None,   # FIX 3 — prevent early cut-off
    }

    try:
        response = http_requests.post(
            f"{LITELLM_BASE_URL}/chat/completions",
            headers=LITELLM_HEADERS,
            json=payload,
            timeout=120,
        )

        if response.status_code == 200:
            result = response.json()
            return (
                result
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "No response generated.")
            )

        if response.status_code == 401:
            return (
                "Authentication failed (401)\n\n"
                "Your `LITELLM_API_KEY` is invalid or expired.\n"
                "Check your `.env` and make sure the key matches what the LiteLLM admin gave you."
            )
        if response.status_code == 404:
            return (
                f"⚠️ **Model not found (404)**\n\n"
                f"The model `{LITELLM_MODEL}` is not configured on your LiteLLM proxy.\n"
                f"Ask your LiteLLM admin which model names are available, "
                f"then update `LITELLM_MODEL` in your `.env`."
            )
        if response.status_code == 429:
            return "⚠️ Rate limit hit (429). Please retry in a moment."
        if response.status_code in (502, 503):
            return (
                f"⚠️ **Proxy unreachable ({response.status_code})**\n\n"
                f"Cannot reach `{LITELLM_BASE_URL}`.\n"
                "Check that the LiteLLM server is running and the IP/port is correct."
            )

        return f"⚠️ LiteLLM error {response.status_code}: {response.text[:300]}"

    except http_requests.exceptions.ConnectionError:
        return (
            f"⚠️ **Connection refused**\n\n"
            f"Could not connect to `{LITELLM_BASE_URL}`.\n"
            "Make sure the LiteLLM proxy server is running."
        )
    except http_requests.exceptions.Timeout:
        return "⚠️ Request timed out after 120s. The model may be overloaded — please retry."
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"


# ==============================
# 7️⃣ Pydantic Models
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
# 8️⃣ Query Classifier
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
# 9️⃣ RDBMS Query Handler
# ==============================

def handle_rdbms_query(question: str, mrn: str) -> str:
    db = SessionLocal()
    mrn = clean_mrn(mrn)
    question_lower = question.lower()

    column_map = {
        "contact":    ["contact", "phone"],
        "name":       ["name"],
        "gender":     ["gender"],
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
            return str(result[0])
        return "Information not found in structured records."
    except Exception as e:
        db.close()
        return f"Database error: {str(e)}"


# ==============================
# 🔟 Upload PDF
# ==============================

@app.post("/api/upload")
async def upload_pdf(mrn: str, file: UploadFile = File(...)):
    try:
        import tempfile
        tmp_dir  = tempfile.gettempdir()          # works on Windows + Linux/Mac
        tmp_path = os.path.join(tmp_dir, file.filename)
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_text = extract_text_from_pdf(tmp_path)

        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Empty PDF")

        store_chunks(mrn, extracted_text)
        return {
            "filename": file.filename,
            "mrn":      clean_mrn(mrn),
            "status":   "Stored in AstraDB"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================
# 1️⃣1️⃣ Load Patient
# ==============================

@app.get("/api/patient/{mrn}", response_model=PatientInfoResponse)
def get_patient(mrn: str):
    db = SessionLocal()
    mrn_clean = clean_mrn(mrn)
    try:
        result = db.execute(
            text("""
                SELECT mrn, name, birth_date, gender, created_at, updated_at
                FROM patient WHERE mrn = :mrn
            """),
            {"mrn": mrn_clean}
        ).fetchone()
        db.close()

        if not result:
            raise HTTPException(status_code=404, detail="Patient not found")

        return PatientInfoResponse(
            mrn=result[0], name=result[1],
            birth_date=str(result[2]) if result[2] else None,
            gender=result[3],
            created_at=str(result[4]) if result[4] else None,
            updated_at=str(result[5]) if result[5] else None,
        )
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==============================
# 1️⃣2️⃣ Patient Query  ← FIX 1 + FIX 4 + FIX 5
# ==============================

@app.post("/api/query")
def query_api(request: QueryRequest):
    mrn        = clean_mrn(request.mrn)
    question   = request.question
    query_type = classify_query(question)

    if query_type == "RDBMS":
        answer = handle_rdbms_query(question, mrn)
        return {"answer": answer, "query_type": "RDBMS", "sources": []}

    result      = vector_search(question, mrn)
    raw_context = clean_context(result.get("answer", ""))   # FIX 4 — clean before use
    sources     = result.get("sources", [])

    # FIX 5 — debug: print what the model actually sees (remove in production)
    print("\n===== CONTEXT SENT TO MODEL =====\n")
    print(raw_context[:2000])
    print("\n=================================\n")

    if not raw_context or raw_context == "No specific information found.":
        return {
            "answer":     "No relevant medical information found in records.",
            "query_type": "VECTOR",
            "sources":    []
        }

    # FIX 1 — strong delimiters + full anti-truncation rules
    nova_prompt = f"""You are a STRICT clinical extraction engine.

You MUST copy text EXACTLY from the context.

==================== CONTEXT START ====================
{raw_context}
==================== CONTEXT END ======================

Clinical Question:
{question}

STRICT RULES:
- DO NOT summarize
- DO NOT paraphrase
- DO NOT modify wording
- ONLY copy exact sentences from the context

COMPLETENESS:
- ALWAYS return FULL sentences
- NEVER return broken or partial sentences
- If a sentence starts, it MUST end
- If a paragraph is relevant, return the FULL paragraph

MULTI-CHUNK HANDLING:
- If answer spans multiple parts, include ALL
- Maintain correct order

ANTI-TRUNCATION:
- Continue writing until ALL relevant text is fully extracted
- Do NOT stop early under any condition

IF NOT FOUND:
Return exactly:
Information not available in the provided records.

OUTPUT:
Return ONLY the extracted text."""

    return {
        "answer":     call_nova(nova_prompt),
        "query_type": "VECTOR",
        "sources":    sources,
    }


# ==============================
# 1️⃣3️⃣ Time Summary  ← LiteLLM powered
# ==============================

@app.post("/api/time_summary", response_model=TimeSummaryResponse)
def time_summary_api(request: TimeSummaryRequest):
    result      = time_based_summary(request.mrn, request.time_range)
    raw_summary = clean_context(result.get("summary", ""))   # FIX 4
    time_range  = result.get("time_range", request.time_range)

    if not raw_summary or raw_summary == "No medical records found.":
        return TimeSummaryResponse(
            summary="No medical records found for this patient.",
            time_range=time_range,
        )

    nova_prompt = f"""You are a clinical AI summarizing a patient discharge record.

RULES:
- Use plain text only, NO markdown (no ###, no **, no *)
- Extract information ONLY from the provided context
- If a field is not found, write: Not found in records

RESPOND IN THIS FORMAT:

DIAGNOSIS:
[from records]

TREATMENT:
[from records]

DISCHARGE MEDICATIONS:
[from records]

STATUS AT DISCHARGE:
[from records]

FOLLOW-UP:
[from records]
"""

    return TimeSummaryResponse(
        summary=call_nova(nova_prompt),
        time_range=time_range,
    )


# ==============================
# 1️⃣4️⃣ Medication Safety  ← LiteLLM powered
# ==============================

@app.post("/api/medication_safety", response_model=MedSafetyResponse)
def medication_safety_api(request: MedSafetyRequest):
    result          = medication_safety_check(request.mrn)
    medications_raw = clean_context(result.get("medications_raw", ""))   # FIX 4
    chunks_used     = result.get("context_chunks_used", 0)

    if not medications_raw or medications_raw == "No medications found.":
        return MedSafetyResponse(
            medications_raw="No medications found in records.",
            interactions_raw="Unable to perform interaction check — no medication data.",
            context_chunks_used=0,
        )

    nova_prompt = f"""You are a clinical pharmacist AI.

Analyze the discharge medications below and provide a safety report.

RULES:
- Use plain text only, NO markdown (no ###, no **, no *)
- Be concise and clinically accurate
- Base analysis ONLY on provided records

RESPOND IN THIS EXACT FORMAT:

MEDICATIONS IDENTIFIED:
[List each drug with dose, frequency, duration]

SAFETY CONCERNS:
[List any GI, renal, cardiovascular risks]

DRUG INTERACTIONS:
[List interactions or write: None identified]

HIGH RISK DRUGS:
[List high-risk drugs or write: None]

MISSING INFORMATION:
[List gaps or write: None]
"""
    return MedSafetyResponse(
        medications_raw=medications_raw,
        interactions_raw=call_nova(nova_prompt),
        context_chunks_used=chunks_used,
    )


# ==============================
# 1️⃣5️⃣ LiteLLM Connection Test
# ==============================

@app.get("/api/test/litellm")
def test_litellm():
    payload = {
        "model":       LITELLM_MODEL,
        "messages":    [{"role": "user", "content": "Reply with exactly: DMH OK"}],
        "max_tokens":  10,
        "temperature": 0.0,
        "stop":        None,
    }
    try:
        r = http_requests.post(
            f"{LITELLM_BASE_URL}/chat/completions",
            headers=LITELLM_HEADERS,
            json=payload,
            timeout=30,
        )
        if r.ok:
            reply = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "status":   "✅ LiteLLM connected",
                "model":    LITELLM_MODEL,
                "base_url": LITELLM_BASE_URL,
                "reply":    reply,
            }
        return {
            "status":   f"❌ HTTP {r.status_code}",
            "detail":   r.text[:300],
            "base_url": LITELLM_BASE_URL,
        }
    except Exception as e:
        return {
            "status":   "❌ Connection failed",
            "error":    str(e),
            "base_url": LITELLM_BASE_URL,
        }


# ==============================
# 1️⃣6️⃣ Health Check
# ==============================

@app.get("/")
def root():
    return {
        "status":  "✅ DMH API running",
        "version": "LiteLLM Proxy",
        "model":   LITELLM_MODEL,
        "proxy":   LITELLM_BASE_URL,
        "test":    "GET /api/test/litellm  ← run this to verify connection",
    }


# ==============================
# 1️⃣7️⃣ Debug — Inspect Stored Chunks
# ==============================

@app.get("/api/debug/chunks/{mrn}")
def debug_chunks(mrn: str):
    """
    Shows exactly what is stored in AstraDB for this MRN.
    Hit: GET /api/debug/chunks/1452925
    """
    from astra_db import collection, clean_mrn as _clean
    mrn_clean = _clean(mrn)

    results = list(collection.find(
        filter={"mrn": mrn_clean},
        limit=20,
        projection={"text": 1, "section": 1, "chunk_index": 1}
    ))

    if not results:
        return {
            "mrn":          mrn_clean,
            "total_chunks": 0,
            "message":      "NO CHUNKS FOUND — PDF not stored or wrong MRN",
            "chunks":       []
        }

    return {
        "mrn":          mrn_clean,
        "total_chunks": len(results),
        "chunks": [
            {
                "index":   doc.get("chunk_index"),
                "section": doc.get("section"),
                "preview": doc.get("text", "")[:200]
            }
            for doc in sorted(results, key=lambda x: x.get("chunk_index", 0))
        ]
    }


@app.get("/api/debug/search/{mrn}")
def debug_search(mrn: str, q: str = "course in the hospital"):
    """
    Runs a raw vector search and shows context sent to Nova.
    Hit: GET /api/debug/search/1452925?q=what+was+the+diagnosis
    """
    from astra_db import vector_search
    result      = vector_search(q, mrn)
    raw_context = result.get("answer", "")
    sources     = result.get("sources", [])

    return {
        "mrn":            clean_mrn(mrn),
        "question":       q,
        "context_length": len(raw_context),
        "context":        raw_context,
        "sources":        sources
    }