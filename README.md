# DMH

# Patient History Summarization System

> **Project:** Deep Agents in Healthcare

---

## 1. Problem Statement

Healthcare providers often lack time to review extensive patient medical records. A single discharge summary can span **6–8 pages**, and patients may have **decades of medical history**.  
This system enables clinicians to ask **natural language queries** over patient records and retrieve **accurate, concise summaries** quickly.

---

## 2. System Overview

### 2.1 Architecture Flow
```
User Query → Query Classifier → Query Processor → Query Router →
[RDBMS Agent | Vector DB Agent | Summarization Agent | Hybrid Agent] →
Response Generator → User
```


### 2.2 Core Components

#### Query Classifier 

First component that analyzes the user query to determine the optimal processing strategy. This prevents unnecessary processing and optimizes cost and speed.

- **RDBMS Agent only:** For simple exact data queries (e.g., "What is the patient's phone number?")
- **Vector DB Agent:** For pure semantic queries (e.g., "Does patient have diabetes symptoms?")
- **Summarization Agent:** For time-based queries (e.g., "Summarize last year")
- **Hybrid Agent:** For complex queries requiring multiple data sources (e.g., "Follow-up procedure for MRN 12345")

#### Query Processor

Splits multi-part queries and extracts entities (patient ID, dates, conditions). Includes temporal normalization to convert relative time references to absolute dates.

**Temporal Normalization Examples:**
- "last year" → 2024-01-01 to 2024-12-31 (based on current date: 2025-01-16)
- "last quarter" → 2024-10-01 to 2024-12-31 (Q4 2024)
- "last 6 months" → 2024-07-16 to 2025-01-16

#### Query Router

Routes queries to appropriate agents based on classification results.

#### RDBMS Agent

Converts natural language to SQL queries using LLM, validates against schema, and executes queries. This agent is critical for the two-step process that ensures accurate ID matching.

#### Vector DB Agent

Performs semantic search with strict metadata filtering. After obtaining document_id from RDBMS queries, filters vector search results to prevent false positives.

#### Summarization Agent

Handles time-based and conditional summaries using a hybrid approach of pre-computed summaries and on-the-fly generation.

#### Response Generator

Formats results into natural language with citations, confidence scores, and source attribution.

---

### 2.3 Two-Step Query Processing Strategy

#### The Solution: Two-Step Process

**Why Two-Step Processing is Mandatory**

Vector similarity search alone cannot guarantee exact ID matching. For example, MRN 12345 and 1234 may appear semantically similar, leading to incorrect patient data retrieval. Hence, exact identifiers must always be resolved using RDBMS before any semantic search.This ensures strict patient data isolation and prevents cross-patient information leakage.

**Final Two-Step Strategy**
**Step 1: Structured Lookup via RDBMS**
- User query is analyzed by the Query Classifier.
- Query Processor extracts entities such as MRN, encounter date, condition, and time range.
- RDBMS Agent generates SQL to:
  - Resolve patient_id from MRN
  - Resolve relevant encounter_id based on date/type
  - Resolve document_id linked to encounters

**Step 2: Content Retrieval (Vector DB or S3)**
- If document size is small or full context is required → load PDF directly from S3.
- If document is large or query is semantic → query Vector DB with strict metadata filters (patient_id, encounter_id, document_id).
- Retrieved content is passed to LLM for extraction/summarization.
---
### 2.4 Hybrid Retrieval Decision Logic 
The system decides retrieval strategy based on query type:
- Exact data queries → RDBMS only (no document access)
- Semantic content queries → RDBMS + Vector DB
- Full document understanding → RDBMS + S3
- Complex medical queries → RDBMS + Vector DB + S3 (Hybrid)
Filtering Rules (Mandatory):
- Vector DB queries must include document_id filter.
- Encounter-level queries must include encounter_id.
- Patient-level queries must always resolve patient_id first.

#### Example Flow: "What is the follow-up procedure for patient MRN 12345?"

1. LLM generates SQL to find patient_id from MRN
2. Query encounters for this patient, ordered by date (most recent first)
3. Retrieve document_ids associated with recent encounters
4. Either load PDFs from S3 OR query vector DB with document_id filter
5. Extract relevant information and generate response
```sql
-- Step 1: Get patient_id
SELECT patient_id FROM patient WHERE mrn = '12345';

-- Step 2: Get recent encounters
SELECT encounter_id, start_date FROM encounter
WHERE patient_id = ''
ORDER BY start_date DESC LIMIT 2;

-- Step 3: Get document IDs (Option A: Simple join)
SELECT document_id, file_path FROM document
WHERE encounter_id IN ();

-- Option B: Complex join in one query
SELECT d.document_id, d.file_path FROM document d
WHERE d.encounter_id IN (
  SELECT encounter_id FROM encounter
  WHERE patient_id = (SELECT patient_id FROM patient WHERE mrn = '12345')
  ORDER BY start_date DESC LIMIT 2
);
```
### 2.5 Application Module Structure

To ensure modularity and maintainability:

- **QueryClassifier** – Determines query type (RDBMS / Semantic / Summary / Hybrid)
- **QueryProcessor** – Extracts entities and normalizes temporal expressions
- **RDBMSService** – Handles SQL generation and execution
- **VectorSearchService** – Performs metadata-filtered semantic search
- **SummarizationService** – Handles pre-computed and on-the-fly summaries
- **StorageService (AWS)** – Manages S3 document access
- **ResponseBuilder** – Formats final output with citations and confidence scores

---

## 3. Data Architecture

### 3.1 RDBMS (FHIR-Compliant Schema)

**Database:** PostgreSQL installed on AWS EC2 

#### Patient Table DDL
```sql
CREATE TABLE patient (
    patient_id VARCHAR(36) PRIMARY KEY,
    mrn VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    gender VARCHAR(10),
    birth_date DATE,
    contact VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

```

#### Encounter Table DDL
```sql
CREATE TABLE encounter (
    encounter_id VARCHAR(36) PRIMARY KEY,
    patient_id VARCHAR(36) NOT NULL,
    encounter_type VARCHAR(50),
    start_date DATETIME NOT NULL,
    end_date DATETIME,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patient(patient_id) ON DELETE CASCADE,
    INDEX idx_patient_date (patient_id, start_date)
);

```

#### Document Table DDL
```sql
CREATE TABLE document (
  document_id VARCHAR(36) PRIMARY KEY,
  encounter_id VARCHAR(36) NOT NULL,
  document_type VARCHAR(50) NOT NULL,
  document_date DATE NOT NULL,
  file_path VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (encounter_id)
    REFERENCES encounter(encounter_id)
    ON DELETE CASCADE,

  INDEX idx_encounter_doc (encounter_id),
  INDEX idx_doc_date (document_date)
);

```

#### Encounter Summary Table DDL (New - For Pre-Computed Summaries)
```sql
  CREATE TABLE encounter_summary (
  summary_id VARCHAR(36) PRIMARY KEY,
  encounter_id VARCHAR(36) NOT NULL,
  patient_id VARCHAR(36) NOT NULL,
  summary_text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (encounter_id)
  REFERENCES encounter(encounter_id)
  ON DELETE CASCADE,
  FOREIGN KEY (patient_id)
  REFERENCES patient(patient_id)
  ON DELETE CASCADE,
  INDEX idx_patient_summary (patient_id)
);

```
### 3.1.2 Enum & Allowed Value Definitions

To ensure schema consistency and prevent invalid data entry, the following enum-like fields have strictly defined allowed values. These values are enforced at the application layer and validated during ingestion.

#### encounter_type
- outpatient
- inpatient
- emergency
- icu
- teleconsultation

#### document_type
- discharge_summary
- lab_report
- prescription
- radiology_report
- progress_note

#### encounter.status
- active
- closed
- cancelled

#### encounter_summary.summary_type
- encounter
- quarterly
- annual
### 3.2 Vector Database

**Technology:** ChromaDB (primary) / FAISS (alternative - to be tested)

#### Indexing Strategy Options:

- **Option 1:** Separate collections per patient MRN (faster queries, better isolation)
- **Option 2:** Single collection with strict metadata filtering (simpler management)

#### Chunking Strategy:

- Section-based chunking (512 tokens maximum per chunk)
- Overlap: 50 tokens between chunks for context continuity
- Preserve section headers in metadata

#### Metadata Schema (CRITICAL - document_id required):

| Metadata Field | Purpose | Example Value |
|---|---|---|
| patient_mrn | Patient-level filtering | "12345" |
| **document_id** | **Exact document matching (prevents false positives)** | **"doc_abc123"** |
| encounter_id | Encounter-level queries | "enc_xyz789" |
| document_date | Temporal filtering | "2024-10-15" |
| document_type | Document type filtering | "discharge_summary" |
| section_type | Section-based retrieval | "medications", "diagnosis" |


### 3.3 File Storage (AWS S3)

#### Organization Structure:
```
s3://bucket-name/
├── {mrn_1}/
│   ├── {encounter_id_1}.pdf
│   ├── {encounter_id_2}.pdf
│   └── ...
├── {mrn_2}/
│   ├── {encounter_id_3}.pdf
│   └── ...
└── ...

Example: s3://healthcare-docs/12345/enc_2024_10_15.pdf
```
#### file_path Field 

The `file_path` column in the document table stores the **full S3 object path**, not just the filename.

**Example:**
s3://healthcare-docs/12345/enc_2024_10_15.pdf

#### Rationale:

- Easy lookup by patient MRN
- Chronological organization by encounter
- Simple file path construction
- Scalable for large patient populations

#### Access Pattern:

1. Query RDBMS to get document_id for specific encounter
2. Retrieve file_path from document table
3. Load PDF from S3 using file_path
4. Process document content

---

## 4. Document Retrieval Strategies

> All three strategies will be implemented and tested empirically with real data to determine which works best under different conditions.

### 4.1 Strategy A: Direct File Loading (No Vector DB)

#### Approach:

- Store PDFs in S3 with organized folder structure
- Retrieve document_id from RDBMS query
- Load entire PDF content into memory
- Pass complete document to LLM with user question

#### Pros:

- Simple implementation - no vector DB needed
- Complete context available to LLM
- Good for small to medium documents
- No risk of missing information due to chunking

#### Cons:

- Expensive for large documents (LLM context token costs)
- Slower processing time for lengthy documents
- May exceed LLM context window for very long histories

#### Best Use Cases:

- Documents under 10 pages (~5,000 tokens)
- Simple question-answering on recent encounters
- When complete context is essential

### 4.2 Strategy B: Vector DB with Strict Metadata Filtering

#### Approach:

- Vectorize all document content during ingestion
- Store comprehensive metadata with each chunk
- After RDBMS query returns document_id, filter vector search by exact document_id match
- Retrieve only semantically relevant chunks

#### Implementation Options:

- **Query-time filtering:** Pass document_id as filter in vector search query
- **Post-retrieval filtering:** Retrieve broader results, then programmatically filter by document_id

#### Pros:

- Efficient for large documents
- Cost-effective (retrieve only relevant chunks)
- Scalable for patients with extensive histories
- Fast semantic search

#### Cons:

- More complex setup and maintenance
- Risk of missing context if chunking is poor
- Requires careful metadata management

#### Best Use Cases:

- Large documents (>20 pages)
- Semantic queries requiring concept matching
- Patients with decades of medical history

### 4.3 Strategy C: Hybrid Approach

#### Approach:

- Use RDBMS for all exact data retrieval (names, dates, IDs, contact info)
- Use Vector DB with filtering for semantic searches
- Combine both sources for complex queries
- Query classifier determines which strategy to use

#### Pros:

- Balances accuracy and efficiency
- Optimizes cost per query type
- Flexible for diverse query patterns

#### Cons:

- Most complex to implement
- Requires sophisticated query classification
- More components to maintain

#### Best Use Cases:

- Production systems with diverse query types
- When optimization of both cost and accuracy is critical

### 4.4 Strategy Testing Plan

We will implement all three strategies and measure:

| Metric | Target | Measurement Method |
|---|---|---|
| Response Time | < 5 seconds | Average time from query to response |
| Accuracy | > 95% | Manual validation against ground truth |
| Cost per Query | < $0.10 | LLM tokens + infrastructure costs |
| Document Size Threshold | TBD | Identify break-even point for each strategy |

#### Expected Outcomes:

- "Strategy A works best when documents are <X pages"
- "Strategy B is more accurate for semantic queries but costs Y% more"
- "Strategy C provides optimal balance for production use"

---
## 5. Key Features

### 5.1 Query Types Supported

#### Type 1: Exact Data Queries (RDBMS Only)

**Examples:**
- "What is the name of patient with MRN 12345?"
- "What is the contact number for this patient?"
- "When was the last encounter for MRN 67890?"

**Processing Flow:**
1. Query Classifier identifies as RDBMS-only query
2. RDBMS Agent generates SQL
3. Execute query and return result directly
4. No document retrieval needed

#### Type 2: Semantic Search Queries (Hybrid)

**Examples:**
- "Does this patient have diabetes?"
- "What symptoms were mentioned in the last visit?"
- "Does Mr. Joglekar have drug interactions?"

**Processing Flow:**
1. Get patient_id from RDBMS using MRN
2. Get relevant document_ids from recent encounters
3. Search Vector DB with semantic query + document_id filter
4. Return relevant chunks with citations

#### Type 3: Time-Based Summary Queries (Summarization Agent)

**Examples:**
- "Summarize encounters in the last year"
- "What happened in Q3 2024?"
- "Give me a summary of the last 6 months"

**Processing Flow:**
1. Normalize temporal reference (e.g., "last year" → 2024-01-01 to 2024-12-31)
2. Query RDBMS for encounters in date range
3. Check encounter_summary table for pre-computed summaries
4. If available, return pre-computed summaries
5. If not, generate on-the-fly from documents
6. Return chronologically ordered summary

#### Type 4: Conditional Summary Queries (Hybrid)

**Examples:**
- "Summary of fracture-related treatments"
- "All diabetes-related encounters"
- "What was the discharge medication for ICU admission on Oct 15?"

> **Scope Clarification:** Conditional summaries are for SINGLE PATIENT only. Cross-patient analytics are out of scope for Phase 1.

**Processing Flow:**
1. Get all encounter_ids for patient from RDBMS
2. Search Vector DB for condition-specific content with encounter_id filters
3. Rank encounters by relevance to condition
4. Generate conditional summary focusing on matching content

### 5.2 Summarization Strategy
Each entry in the encounter_summary table represents a pre-generated summary for a patient over a specific time period defined by period_start_date and period_end_date.
The summary_text is derived from all documents associated with encounters that fall within the specified time period.

#### Pre-Computed Summaries (Recommended Approach)

**Rationale:**
- Past encounters don't change once closed
- Common time windows (last year, last quarter) can be pre-generated
- Faster retrieval for frequently requested summaries
- Significant cost savings (avoid regenerating same summaries)

**Implementation:**
- **Encounter-Level Summaries:** Generated when encounter status changes to "closed". encounter_id is populated.
- **Quarterly Summaries:** Aggregated from encounter summaries at end of each quarter. encounter_id is NULL.
- **Annual Summaries:** Aggregated from quarterly summaries at year-end. encounter_id is NULL.

**Example for Patient with 5 Years of History:**
```
Example — Encounter Summary
- encounter_id: E123
- period: 2026-01-10 to 2026-01-10
- summary_type: encounter

Example — Quarterly Summary
- encounter_id: NULL
- period: 2025-10-01 to 2025-12-31
- summary_type: quarterly

Example — Annual Summary
- encounter_id: NULL
- period: 2025-01-01 to 2025-12-31
- summary_type: annual

```

#### On-the-Fly Summary Generation

**When to Use:**
- Custom time windows not matching pre-computed periods
- Very recent encounters not yet summarized
- First-time queries for new patients

**Progressive Summarization Technique:**

For patients with extensive histories (>5 years):
1. Start with oldest encounter summary
2. Progressively add details from each subsequent encounter
3. Maintain running summary with incremental updates
4. Final summary captures entire timeline without overwhelming LLM context

### TIME-BASED Logic:

For time-based queries such as ‘last 6 months’, the system always checks for the largest applicable pre-computed summaries first and generates on-the-fly summaries only for uncovered recent periods.

---
  
## 6. Implementation Plan

### Phase 1 : Setup & Data Preparation

- Development environment setup
- RDBMS schema implementation (PostgreSQL on EC2)
- DDL script creation and database initialization
- Synthetic data generation (awaiting PII-scrubbed samples from Angelin)
- AWS S3 bucket setup and folder structure
- GitHub repository setup with issues tracking

### Phase 2 : Core Agents Development

- **Task 1:** Query Classifier Agent implementation
- **Task 2:** Query Processor with temporal normalization
- **Task 3:** RDBMS Agent (SQL generation & execution)
- **Task 4:** Vector DB setup and document ingestion
- **Task 5:** Document retrieval from S3

### Phase 3 : Advanced Features & Integration

- **Task 6:** Vector DB Agent with metadata filtering
- **Task 7:** Summarization Agent (pre-computed + on-the-fly)
- **Task 8:** Response Generator with citations
- **Task 9:** Agent orchestration using LangGraph
- **Task 10:** Implement all three retrieval strategies

### Phase 4 : Testing & Optimization

- **Task 11:** Strategy comparison testing (A vs B vs C)
- **Task 12:** Performance optimization
- **Task 13:** Accuracy validation with ground truth
- **Task 14:** Cost analysis per query type
- **Task 15:** Security review and HIPAA compliance check

### Phase 5 : Deployment & User Testing

- **Task 16:** AWS EC2 deployment (PostgreSQL + Application)
- **Task 17:** Streamlit UI development
- **Task 18:** User acceptance testing
- **Task 19:** Documentation and handover
- **Task 20:** Hospital integration planning (if real data available)

---
## 7. Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Backend Framework | Python + FastAPI | With streaming support for real-time responses |
| LLM | Claude Sonnet 4.5 | Primary model for all agent tasks |
| RDBMS | PostgreSQL on AWS EC2 | 
| Vector Database | ChromaDB (primary)<br/>FAISS (alternative) 
| Agent Framework | **LangGraph** |
| File Storage | AWS S3 | Organized by MRN/encounter_id structure |
| Frontend | Streamlit | 
| Infrastructure | AWS EC2 | Single EC2 instance for database + application |
| Development Tools | GitHub, VS Code, Docker | Version control and containerization |

AWS Bedrock Agent for:
- Session-based conversation memory
- Context retention across multi-turn clinical queries
- Reducing prompt reconstruction overhead

---
## 8. API Schema (FastAPI)

### 8.1 Query Endpoint
```http
POST /api/query

Request:
{
  "query": "What is the follow-up procedure for patient MRN 12345?",
  "user_id": "string",
  "session_id": "string (optional)"
}

Response (Streaming Supported):
{
  "answer": "string",
  "sources": [
    {
      "document_id": "string",
      "document_type": "string",
      "excerpt": "string",
      "page_number": "int",
      "relevance_score": "float"
    }
  ],
  "query_type": "hybrid | rdbms | semantic | summary",
  "processing_time_ms": "float",
  "confidence_score": "float",
  "strategy_used": "A | B | C"
}
```

### 8.2 Patient Lookup Endpoint
```http
GET /api/patient/{mrn}

Response:
{
  "patient_id": "string",
  "mrn": "string",
  "name": "string",
  "gender": "string",
  "birth_date": "YYYY-MM-DD",
  "encounter_count": "int",
  "last_encounter_date": "YYYY-MM-DD"
}
```

### 8.3 Summarization Endpoint
```http
POST /api/summarize

Request:
{
  "mrn": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "condition_filter": "string (optional)",
  "summary_type": "encounter | quarterly | annual"
}

Response:
{
  "summary": "string",
  "encounter_count": "int",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "sources": [
    {
      "encounter_id": "string",
      "encounter_date": "YYYY-MM-DD",
      "encounter_type": "string"
    }
  ],
  "summary_type": "pre-computed | on-the-fly",
  "processing_time_ms": "float"
}
```

### 8.4 Health Check Endpoint
```http
GET /api/health

Response:
{
  "status": "healthy | degraded | unhealthy",
  "database": "connected | disconnected",
  "vector_db": "connected | disconnected",
  "s3": "accessible | inaccessible",
  "llm": "available | unavailable"
}
```

---

## 9. Security & Compliance

- HIPAA compliant
- Encryption at rest and in transit
- Role-based access control (RBAC)
- Audit logging
- Synthetic data for development
- NDA required for real patient data

---

## 10. Sample Queries with Expected Processing

**Query 1: "What is the follow-up procedure for patient MRN 12345?"**

**Type:** Hybrid

**Flow:**
1. Classify query as follow-up + patient-specific.
2. Extract MRN = 12345.
3. SQL → Patient table → get patient_id.
4. SQL → Encounter table → get most recent closed encounter.
5. SQL → Document table → get document_id.
6. If document < 10 pages → load from S3.
7. Else → Vector DB search filtered by document_id.
8. LLM extracts follow-up procedure.
9. Response returned with document citation.

**Query 2: "Does this patient have drug interactions?"**

**Type:** Semantic

**Flow:**
1. Extract MRN → get patient_id.
2. SQL → get most recent encounter_ids (ordered by date, limited window)
3. SQL → get related document_ids.
4. Vector DB search with filters (document_id, section_type = medications).
5. LLM checks interaction patterns.
6. Answer returned with confidence score.

**Query 3: "Summarize encounters in the last 6 months"**

**Type:** Time-based Summary

**Flow:**
1. Normalize time range.
2. SQL → get encounters within date range.
3. SQL → Encounter table → get encounter_ids for patient_id within date range.
4. Check encounter_summary table.
5. If summaries exist → return directly.
6. Else → retrieve documents and generate on-the-fly summary.

**Query 4: "What was the discharge medication for ICU admission on Oct 15?"**

**Type:** Hybrid

**Flow:**
1. Extract MRN + date.
2. SQL → get encounter_id on Oct 15.
3. SQL → get discharge document_id.
4. Load document from S3.
5. LLM extracts medication section.

**Query 5: "What is the contact number for MRN 12345?"**

**Type:** RDBMS Only

**Flow:**
1. Extract MRN.
2. SQL → Patient table.
3. Return result directly.

---
