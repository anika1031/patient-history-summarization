# DMH

# Patient History Summarization System

> **Project:** Deep Agents in Healthcare

---

## 📌 Problem Statement

Healthcare providers often lack time to review extensive patient medical records. A single discharge summary can span **6–8 pages**, and patients may have **decades of medical history**.  
This system enables clinicians to ask **natural language queries** over patient records and retrieve **accurate, concise summaries** quickly.

---

## 🏗️ System Overview

### High-Level Architecture

<img width="268" height="309" alt="image" src="https://github.com/user-attachments/assets/2666f82c-d037-4e77-8a0d-2bc419dadac5" />


### Core Components

- **Query Processor**
  - Splits multi-part queries
  - Extracts entities (patient ID, MRN, dates, conditions)

- **Query Router**
  - Routes queries based on type:
    - Concrete data (MRN, names, dates) → RDBMS
    - Semantic queries (conditions, history) → Vector DB
    - Complex queries → Both

- **RDBMS Agent**
  - Converts natural language to SQL
  - Validates and executes queries

- **Vector DB Agent**
  - Performs semantic search
  - Applies metadata filtering (MRN, date ranges, document type)

- **Response Generator**
  - Produces natural language output
  - Includes citations for traceability

---

## 🗄️ Data Architecture

### RDBMS (FHIR-Compliant Schema)

**Patient Table**
- patient_id
- mrn
- name
- gender
- birth_date
- contact

**Encounter Table**
- encounter_id
- patient_id
- practitioner_id
- encounter_type
- start_date
- end_date

**Document Table**
- document_id
- encounter_id
- patient_id
- document_type
- document_date
- vector_index_id

### Vector Database

- **Technology:** ChromaDB / FAISS
- **Indexing Strategy:**
  - Separate vector index per patient MRN
  - Metadata:
    - patient_mrn
    - document_date
    - document_type
    - section_type
  - Section-based chunking (max 512 tokens)

---

## ✨ Key Features

### Supported Query Types

1. **Exact Lookups**  
   _"What is the name of patient with MRN 12345?"_

2. **Semantic Search**  
   _"Does this patient have diabetes?"_

3. **Time-Based Queries**  
   _"Summarize encounters in the last year"_

4. **Conditional Summaries**  
   _"Summary of fracture-related treatments"_

### Dynamic Summarization

- Chronologically sorted documents from RDBMS
- Filtering by time period or medical condition
- On-the-fly summarization (no pre-generated summaries)
- Progressive summarization for long medical histories

---

## 🚀 Implementation Plan

| Phase | Duration | Description |
|------|----------|-------------|
| Phase 1 | Week 1–2 | Setup, synthetic data, FHIR schema |
| Phase 2 | Week 3–4 | Core agents (Router, SQL, Vector Search) |
| Phase 3 | Week 5–6 | Integration, Response Generator, UI |
| Phase 4 | Week 7–8 | Testing, optimization, security |
| Phase 5 | Week 9–10 | Hospital integration, user testing |

---

## 🧰 Technology Stack

### Backend
- Python
- FastAPI

### LLM
- Claude Sonnet 4.5

### Databases
- PostgreSQL / MySQL
- ChromaDB / FAISS

### Agent Framework
- LangChain

### Frontend
- Streamlit (Prototype)

### Infrastructure
- AWS (EC2, RDS, S3)

---

## 🔐 Security & Compliance

- HIPAA compliant
- Encryption at rest and in transit
- Role-based access control (RBAC)
- Audit logging
- Synthetic data for development
- NDA required for real patient data

---

## 📊 Success Metrics

- Query response time: **< 5 seconds**
- Concrete data accuracy: **100%**
- Semantic relevance: **> 85%**
- Time saved per revi
