## Patient History Summarization

> Ask any clinical question in plain English. Get an instant, accurate answer extracted directly from the patient's discharge summary — grounded in real records, zero hallucination.

---

##  What is Patient history summarization ?

PHS is a full-stack AI clinical decision support system built for hospitals. It solves a real problem: doctors and medical staff waste significant time manually reading through lengthy patient discharge summaries to find specific information.

PHS lets a clinician type a question like:

> *"What medications was the patient discharged with?"*
> *"What was the course in the hospital?"*
> *"What are the red flag signs to watch for?"*

And receive an instant, verbatim answer extracted from the patient's own PDF records — with no guessing, no summarization, no hallucination.

---

##  Key Features

###  Patient Query (RAG-Powered)
Natural language clinical Q&A grounded exclusively in the patient's discharge summary. Uses vector similarity search to retrieve the most relevant section, then extracts the exact answer using a strict clinical LLM prompt.

###  Time-Based Summary
Generates a structured clinical summary from priority sections: `DIAGNOSIS`, `DISCHARGE MEDICATIONS`, `STATUS AT DISCHARGE`, `FOLLOW-UP`, and `ADVICE ON DISCHARGE`. Useful for handover notes and outpatient consultations.

###  Medication Safety Check
Automatically extracts all discharge medications and runs an AI-powered drug interaction analysis. Flags high-risk medications (anticoagulants, NSAIDs, opioids, narrow therapeutic index drugs) and missing dosage information.

###  PDF Upload & Indexing
Multi-step ingestion pipeline: Upload PDF → Extract text → Chunk by clinical section → Generate vector embeddings → Index in AstraDB. Full progress shown live in the UI.

###  Hybrid Query Router
Automatically classifies every question: structured queries (name, date of birth, contact number) are routed directly to the SQL database; clinical queries go through the full RAG vector pipeline.

---

##  System Architecture

```
┌─────────────────────────────────────────┐
│         Clinician / Doctor              │
│    Natural language query + MRN         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      Streamlit Frontend  (app.py)       │
│  Patient Query | Time Summary |         │
│  Medication Safety | Upload Records     │
└────────────────┬────────────────────────┘
                 │  HTTP REST
                 ▼
┌─────────────────────────────────────────┐
│      FastAPI Backend  (main.py)         │
│                                         │
│         classify_query()                │
│        /              \                 │
│       SQL            VECTOR             │
└──────┬────────────────────┬────────────┘
       │                    │
       ▼                    ▼
┌──────────────┐   ┌─────────────────────┐
│  SQL Database│   │  AstraDB Vector DB  │
│  name, DOB,  │   │  discharge summary  │
│  contact     │   │  chunks + embeddings│
└──────────────┘   └──────────┬──────────┘
                               │ top 3 chunks
                               ▼
                   ┌─────────────────────┐
                   │ Nova Lite via       │
                   │ LiteLLM Proxy       │
                   │ verbatim extraction │
                   └──────────┬──────────┘
                               │ answer
                               ▼
                   ┌─────────────────────┐
                   │  Streamlit UI       │
                   └─────────────────────┘
```

---

##  How the RAG Pipeline Works

**RAG (Retrieval Augmented Generation)** is the core AI design pattern. It retrieves before generating — so the LLM can only answer from real patient records.

```
INGESTION FLOW
──────────────
Upload PDF
  → Extract text          (pdfplumber / pdfminer)
  → split_by_sections()   (4-pass clinical section chunker)
  → generate_embedding()  (vector conversion)
  → Delete old chunks     (collection.delete_many())
  → Store in AstraDB      ($vector + MRN + section metadata)

QUERY FLOW
──────────
User question + MRN
  → classify_query()
      ├─ SQL path  → direct database query → structured answer
      └─ VECTOR path
            → generate_embedding(question)
            → AstraDB similarity search → top 3 chunks
            → extract_relevant_portion()
            → clean_context()
            → nova_prompt (strict extraction rules)
            → call_nova() via LiteLLM
            → Answer displayed in UI
```

### The 4-Pass Clinical Section Chunker

The most critical component. Standard character-based chunking destroys clinical context — splitting mid-sentence across sections. DMH uses a 4-pass strategy:

| Pass | Strategy | Catches |
|------|----------|---------|
| 1 | Known headers list | `DIAGNOSIS`, `COURSE IN THE HOSPITAL`, `DISCHARGE MEDICATIONS`, `FOLLOW-UP`, etc. (33 headers) |
| 2 | Structural regex `\n(?=[A-Z][A-Z\s/]{4,}:)` | Custom headers not in the static list |
| 3 | Paragraph split on `\n\n` | Documents with no headers |
| 4 | 500-character character windows | Last resort fallback |

Each chunk is stored as a **complete, self-contained unit** — no broken sentences, no lost context.

---

##  Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend UI | Streamlit | Clinical dashboard with 4 feature modules |
| Backend API | FastAPI (Python) | High-performance async REST API |
| Vector Database | AstraDB (DataStax) | Semantic similarity search at scale |
| LLM Proxy | LiteLLM | Model-agnostic proxy for LLM routing |
| Language Model | Nova Lite | Clinical text extraction |
| PDF Extraction | pdfplumber / pdfminer | Raw text extraction from clinical PDFs |
| Embeddings | embedding_utils.py | Text → vector conversion |
| Relational DB | SQLAlchemy + SQL | Structured patient metadata |
| Config | python-dotenv | Secure API key management |

---

##  Project Structure

```
dmh/
├── main.py                  # FastAPI backend — all API endpoints
├── astra_db.py              # AstraDB connection, chunking, vector search
├── app.py                   # Streamlit frontend
├── embedding_utils.py       # Embedding generation
├── pdf_utils.py             # PDF text extraction
├── db.py                    # SQLAlchemy session setup
├── .env                     # Environment variables (not committed)
├── requirements.txt         # Python dependencies
└── README.md
```

---

##  Setup & Installation

### Prerequisites
- Python 3.10+
- AstraDB account (free tier works) — [astra.datastax.com](https://astra.datastax.com)
- LiteLLM proxy server running with Nova Lite (or any OpenAI-compatible model)


### 1. Create and activate virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the root directory:

```env
# AstraDB
ASTRA_DB_API_ENDPOINT=https://YOUR-DB-ID-region.apps.astra.datastax.com
ASTRA_DB_APPLICATION_TOKEN=AstraCS:YOUR_TOKEN_HERE

# LiteLLM Proxy
LITELLM_API_KEY=your-litellm-api-key
LITELLM_BASE_URL=http://your-litellm-server:4000
LITELLM_MODEL=nova-lite
```

### 4. Run the FastAPI backend
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Run the Streamlit frontend
```bash
streamlit run app.py
```

### 6. Verify the connection
Open `http://localhost:8000/api/test/litellm` — you should see `✅ LiteLLM connected`.

---

##  API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload and index a patient PDF |
| `GET` | `/api/patient/{mrn}` | Get structured patient info |
| `POST` | `/api/query` | Ask a clinical question (RAG) |
| `POST` | `/api/time_summary` | Generate time-based clinical summary |
| `POST` | `/api/medication_safety` | Run medication safety check |
| `GET` | `/api/test/litellm` | Test LiteLLM proxy connection |
| `GET` | `/api/debug/chunks/{mrn}` | Inspect stored AstraDB chunks |
| `GET` | `/api/debug/search/{mrn}` | Debug vector search for a query |
| `GET` | `/` | Health check |

Full interactive API documentation is auto-generated at `http://localhost:8000/docs`.

---

##  Example Usage

### Upload a discharge summary
```bash
curl -X POST "http://localhost:8000/api/upload?mrn=1452925" \
  -F "file=@Discharge_Summary_Patient.pdf"
```

### Ask a clinical question
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"mrn": "1452925", "question": "What was the course in the hospital?"}'
```

### Response
```json
{
  "answer": "The patient was evaluated in an outpatient/short-stay setting. The clinical course indicated that the patient was monitored for approximately 4 hours. The patient's vitals remained stable throughout the monitoring period. No intervention was required during the stay...",
  "query_type": "VECTOR",
  "sources": [
    {
      "chunk_index": 4,
      "section": "COURSE IN THE HOSPITAL",
      "preview": "The patient was evaluated in an outpatient..."
    }
  ]
}
```

---

##  Anti-Hallucination Design

DMH is specifically engineered to prevent the LLM from making up clinical information:

- **RAG grounding** — the model only sees the retrieved patient chunks, not general medical knowledge
- **Strong context delimiters** — `==== CONTEXT START ====` / `==== CONTEXT END ====` prevent prompt injection
- **Strict extraction prompt** — explicitly instructs the model: DO NOT summarize, DO NOT paraphrase, ONLY copy exact sentences from context
- **`stop=None`** — prevents early truncation of long answers
- **`clean_context()`** — normalizes raw AstraDB output before sending to the model

---

##  Debugging

If answers are returning "Information not available in the provided records":

```bash
# Step 1: Check if chunks are stored for this MRN
GET http://localhost:8000/api/debug/chunks/1452925

# Step 2: Check what context the vector search returns
GET http://localhost:8000/api/debug/search/1452925?q=what+was+the+diagnosis

# Step 3: Check FastAPI terminal logs for:
# ===== CONTEXT SENT TO MODEL =====
# (first 2000 chars of context printed here)
```

Common issues:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `total_chunks: 0` | MRN stored differently | Re-upload PDF with correct MRN |
| Context exists but "not available" | Nova Lite prompt issue | Check LiteLLM connection |
| Chunking fails | PDF text encoding issue | Check pdfplumber extraction output |
| `[Errno 2] No such file` on Windows | `/tmp/` path used | Use `tempfile.gettempdir()` |

---

##  Future Scope

- Multi-patient comparison queries across hospital cohorts
- Real-time vitals and lab result integration
- Role-based access control (doctor / nurse / admin)
- Cloud deployment on AWS / Azure with HIPAA-compliant storage
- Fine-tuned clinical LLM replacing general-purpose Nova Lite
- Confidence score and source citation shown alongside every answer

---

##  Authors

Developed as a Final Year B.Tech Project at **D Y Patil International University, Akurdi, Pune**
School of Computer Science, Engineering & Applications

| Name | Roll Number |
|------|------------|
| Anika Pandit | 20220802196 |
| Kanishka Sharma | 20220802179 |
| Sanika Gavkadkar | 20220802038 |



---


> **Note:** This system is intended for academic and demonstration purposes. For production clinical deployment, additional validation, security hardening, and regulatory compliance (HIPAA / DPDP Act) would be required.
