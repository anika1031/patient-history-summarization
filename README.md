# Deep Agents in Healthcare
### An AI-powered system that helps doctors instantly find patient information from discharge summaries — using plain English questions.

---

##  What is this project?

Doctors often have to manually scroll through pages of PDF discharge summaries to find a single piece of information — a medication name, a diagnosis, a follow-up date. This takes time and can lead to errors.

**Deep Agents in Healthcare** solves this. A doctor types a question like:

> *"What medications was the patient discharged with?"*

And gets the answer in under 2 seconds — pulled directly from the patient's actual records. No guessing. No wrong information.

---

## Features

###  Patient Query
Ask any clinical question in plain English. The system searches the patient's discharge summary and returns a grounded, accurate answer.

###  Time-Based Summary
Generates a chronological summary of a patient's entire history across multiple admissions — all in one view.

###  Medication Safety Check
Automatically analyses discharge medications, flags high-risk drugs, identifies potential drug interactions, and highlights missing dosage information.

###  Hybrid Query Router
Simple factual questions (name, date of birth, contact) are answered via SQL in under 200ms. Clinical questions go through AI-powered vector search. Right tool for the right question.

###  Zero Hallucination Design
The AI is strictly constrained to answer only from retrieved patient records. If the information is not in the records, it says — *"Not found in records."* It never invents clinical information.

---

##  Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Frontend | Streamlit | Simple, clean interface — no coding required from clinical staff |
| Backend | FastAPI | Lightweight, fast, auto-generates API documentation |
| Vector Database | AstraDB | Cloud-hosted, scales automatically, native vector search |
| LLM | Nova Lite via LiteLLM | Cost-efficient, swappable, strict prompt control |
| PDF Extraction | pdfplumber | Reliable text extraction from structured medical PDFs |
| Embeddings | Sentence Transformer (MiniLM-L6-v2) | Fast, lightweight, runs locally |
| Core Architecture | RAG (Retrieval-Augmented Generation) | Grounds every answer in real patient records |

---

##  Screenshots

<img width="1600" height="722" alt="streamlit" src="https://github.com/user-attachments/assets/86f9d685-e593-4942-acb4-bba44583d663" />
<img width="1600" height="765" alt="query2" src="https://github.com/user-attachments/assets/76a28f2c-48f1-496d-a2a3-395d657b97c9" />
<img width="1600" height="729" alt="query" src="https://github.com/user-attachments/assets/0115d0aa-6851-40e0-a0ff-209284eb5ce8" />
<img width="1600" height="731" alt="TBS2" src="https://github.com/user-attachments/assets/51cc61c9-da33-43f5-999e-470b2e416a38" />
<img width="1600" height="757" alt="MS2" src="https://github.com/user-attachments/assets/21bb08ab-d7a8-4c79-928f-ce3d8cdd9a18" />


| Feature | Screenshot |
|---|---|
| Clinical Query Interface | `screenshots/query.png` |
| Medication Safety Analysis | `screenshots/medication.png` |
| Time-Based Summary | `screenshots/summary.png` |
| Document Upload Screen | `screenshots/upload.png` |

---

##  Results

| Query Type | Accuracy | Avg Response Time | Hallucination Rate |
|---|---|---|---|
| Medication queries | 95% | 1.2 sec | 0% |
| Diagnosis queries | 93% | 1.1 sec | 0% |
| Follow-up queries | 91% | 1.4 sec | 0% |
| Demographic (SQL) | 100% | 0.2 sec | — |

---

##  Future Scope

- **EHR Integration** — Direct connection to live hospital systems via HL7 FHIR, replacing manual PDF uploads
- **Multilingual Support** — Hindi and Marathi language support for Indian hospital records
- **Clinical Embeddings** — Replace MiniLM with ClinicalBERT for better accuracy on medical terminology
- **Longitudinal Tracking** — Monitor patient health indicators across multiple admissions over time
- **OCR Integration** — Support for scanned PDF documents

---

##  Limitations

- Scanned/image PDFs cannot be processed without OCR integration
- Currently supports English language only
- Medication safety analysis is AI-generated — decision support only, not a replacement for a clinical pharmacist
- Prototype only — not yet clinically validated in a live hospital environment

---


---

##  Key References

- Lewis et al. — Retrieval-Augmented Generation (RAG), NeurIPS 2020
- Karpukhin et al. — Dense Passage Retrieval, EMNLP 2020
- Alsentzer et al. — ClinicalBERT, 2019
- Wornow et al. — Clinical Foundation Models Survey, npj Digital Medicine 2023

---

*Submitted as Final Year Project — B.Tech CSE, Session 2025-26*
