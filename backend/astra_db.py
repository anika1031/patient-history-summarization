# ─────────────────────────────────────────
# 1️⃣ Imports & Setup
# ─────────────────────────────────────────

from astrapy.client import DataAPIClient
from dotenv import load_dotenv
import os
import re

from embedding_utils import generate_embedding

load_dotenv()


# Astra DB Config
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")

# Connect to Astra DB
astra_client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
db = astra_client.get_database_by_api_endpoint(ASTRA_DB_API_ENDPOINT)
collection = db.get_collection("patient_chunks")
# collection.delete_many({})
# print("✅ All old embeddings deleted")

# ─────────────────────────────────────────
# 2️⃣ MRN CLEANER
# ─────────────────────────────────────────

def clean_mrn(mrn) -> str:
    cleaned = (
        str(mrn)
        .upper()
        .replace("MRN", "")
        .replace("MRD", "")
        .replace("#", "")
        .replace(" ", "")
        .replace(":", "")
        .strip()
    )
    return f"MRN{cleaned.zfill(3)}"


# ─────────────────────────────────────────
# 3️⃣ SECTION-BASED CHUNKING
# ─────────────────────────────────────────

SECTION_HEADERS = [
    "CHIEF COMPLAINT",
    "HISTORY OF PRESENT ILLNESS",
    "PAST MEDICAL HISTORY",
    "PHYSICAL EXAMINATION",
    "INVESTIGATIONS",
    "DIAGNOSIS",
    "TREATMENT",
    "DISCHARGE MEDICATIONS",
    "ADVICE ON DISCHARGE",
    "FOLLOW-UP",
    "SPECIAL NEEDS",
    "RED FLAG SIGNS",      
    "PROCEDURE DETAILS",
    "PROCEDURE PERFORMED",
    "STATUS AT DISCHARGE",
    "REFERENCE",
    "CONTACT DETAILS",
    "IN CASE OF EMERGENCY",
    "PREPARED BY",
    "APPROVED BY",
    "SURGEON",              
    "HISTORY",
    "EXAMINATION",
    "DISCHARGE SUMMARY",
]

def split_by_sections(text: str) -> list:
    """
    Split discharge summary into labeled section chunks using known headers.
    Returns list of dicts: {"section": str, "text": str}
    """
    pattern = r'(' + '|'.join(re.escape(h) for h in SECTION_HEADERS) + r')[:\s]*'
    parts = re.split(pattern, text, flags=re.IGNORECASE)

    chunks = []
    i = 1
    while i < len(parts) - 1:
        section_name = parts[i].strip().upper()
        section_body = parts[i + 1].strip()

        if section_body and len(section_body) > 10:
            chunks.append({
                "section": section_name,
                "text": f"{section_name}:\n{section_body}"
            })
        i += 2

    # Fallback: if no sections detected, chunk by character size
    if not chunks:
        print("⚠️ No sections detected — falling back to character chunking")
        chunk_size = 500
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i + chunk_size].strip()
            if len(chunk_text) > 20:
                chunks.append({
                    "section": f"CHUNK_{i // chunk_size}",
                    "text": chunk_text
                })

    return chunks


# ─────────────────────────────────────────
# 4️⃣ STORE CHUNKS
# ─────────────────────────────────────────

def store_chunks(mrn: str, raw_text: str):
    """
    Delete old embeddings for this MRN, re-chunk by section, and store.
    Pass raw discharge summary text as `raw_text`.
    """
    mrn = clean_mrn(mrn)

    # Delete old records for this MRN before re-ingesting
    delete_result = collection.delete_many({"mrn": mrn})
    print(f"🗑️ Deleted old chunks for {mrn}: {delete_result.deleted_count} records")

    chunks = split_by_sections(raw_text)
    print(f"📦 Storing {len(chunks)} section-chunks for MRN: {mrn}")

    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk["text"])

        collection.insert_one({
            "mrn": mrn,
            "chunk_index": i,
            "section": chunk["section"],
            "text": chunk["text"],
            "$vector": embedding
        })

    print(f"✅ Stored {len(chunks)} sections for {mrn}")


# ─────────────────────────────────────────
# 5️⃣ RELEVANT LINE EXTRACTOR
# ─────────────────────────────────────────

STOPWORDS = {
    "what", "was", "the", "is", "did", "with", "for", "patient",
    "a", "an", "of", "in", "on", "to", "and", "or", "that",
    "this", "are", "were", "has", "have", "been", "at", "by"
}


# ─── Fix 2: Strip section header from chunk body in display ───
def extract_relevant_portion(text: str, question: str, max_lines: int = 20) -> str:
    keywords = set(question.lower().split()) - STOPWORDS

    lines = text.split("\n")
    scored_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # ✅ Fix 2: Skip the section header line (already shown in 📄 label)
        is_header = any(
            line.upper().startswith(h) for h in SECTION_HEADERS
        )
        if is_header:
            continue

        score = sum(1 for kw in keywords if kw in line.lower())
        scored_lines.append((score, line))

    relevant = [line for score, line in scored_lines if score > 0]

    if not relevant:
        # Fallback: return all non-header lines
        relevant = [line for _, line in scored_lines[:max_lines]]

    return "\n".join(relevant[:max_lines])
# ─────────────────────────────────────────
# 6️⃣ VECTOR SEARCH (RAG)
# ─────────────────────────────────────────

# ─── Fix 1: Remove duplicate header in vector_search ───
def vector_search(question: str, mrn: str) -> dict:
    mrn = clean_mrn(mrn)
    query_vector = generate_embedding(question)

    results = list(collection.find(
        filter={"mrn": mrn},
        sort={"$vector": query_vector},
        limit=3,
        projection={"text": 1, "chunk_index": 1, "section": 1}
    ))

    if not results:
        return {"answer": "No relevant medical information found.", "sources": []}

    formatted_parts = []

    for doc in results:
        text = doc.get("text", "").strip()
        section = doc.get("section", "")

        if len(text) < 20:
            continue

        relevant = extract_relevant_portion(text, question)

        if relevant:
            # ✅ Fix 1: text already contains section header, don't repeat it
            formatted_parts.append(f"📄 **{section}**\n{relevant}")

    # Deduplicate
    seen = set()
    unique_parts = []
    for part in formatted_parts:
        if part not in seen:
            seen.add(part)
            unique_parts.append(part)

    answer = "\n\n---\n\n".join(unique_parts) if unique_parts else "No specific information found."

    sources = [
        {
            "chunk_index": doc.get("chunk_index", i),
            "section": doc.get("section", "Unknown"),
            "preview": doc["text"][:100] + "..."
        }
        for i, doc in enumerate(results)
    ]

    return {"answer": answer, "sources": sources}
# ─────────────────────────────────────────
# 7️⃣ TIME-BASED SUMMARY
# ─────────────────────────────────────────

def time_based_summary(mrn: str, time_range: str = "Last 6 Months") -> dict:
    mrn = clean_mrn(mrn)

    results = list(collection.find(
        filter={"mrn": mrn},
        limit=5,
        projection={"text": 1, "chunk_index": 1, "section": 1}
    ))

    if not results:
        return {
            "summary": "No medical records found.",
            "time_range": time_range
        }

    results.sort(key=lambda x: x.get("chunk_index", 0))

    # Pick clinically meaningful sections for summary
    priority_sections = {
        "DIAGNOSIS", "DISCHARGE MEDICATIONS",
        "STATUS AT DISCHARGE", "FOLLOW-UP", "ADVICE ON DISCHARGE"
    }

    summary_parts = []
    for doc in results:
        section = doc.get("section", "").upper()
        text = doc.get("text", "").strip()

        if section in priority_sections and text:
            summary_parts.append(f"**{section}**\n{text[:400]}")

    # Fallback if no priority sections found
    if not summary_parts:
        summary_parts = [doc["text"][:300] for doc in results]

    summary = "\n\n---\n\n".join(summary_parts)

    return {
        "summary": summary,
        "time_range": time_range
    }


# ─────────────────────────────────────────
# 8️⃣ MEDICATION SAFETY CHECK
# ─────────────────────────────────────────

def medication_safety_check(mrn: str) -> dict:
    mrn = clean_mrn(mrn)

    query_vector = generate_embedding("discharge medications prescriptions drugs dosage")

    results = list(collection.find(
        filter={"mrn": mrn},
        sort={"$vector": query_vector},
        limit=3,
        projection={"text": 1, "section": 1}
    ))

    if not results:
        return {
            "medications_raw": "No medications found.",
            "interactions_raw": "No data.",
            "context_chunks_used": 0
        }

    # Prefer the DISCHARGE MEDICATIONS section specifically
    med_chunks = [
        doc for doc in results
        if "MEDICATION" in doc.get("section", "").upper()
    ]

    # Fall back to all results if section not found
    if not med_chunks:
        med_chunks = results

    medications = "\n\n".join(
        doc["text"].strip()
        for doc in med_chunks
        if len(doc.get("text", "").strip()) > 20
    )

    return {
        "medications_raw": medications,
        "interactions_raw": "⚠️ Interaction check not available (LLM removed)",
        "context_chunks_used": len(med_chunks)
    }