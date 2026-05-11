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
ASTRA_DB_API_ENDPOINT         = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN    = os.getenv("ASTRA_DB_APPLICATION_TOKEN")

# Connect to Astra DB
astra_client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
db           = astra_client.get_database_by_api_endpoint(ASTRA_DB_API_ENDPOINT)
collection   = db.get_collection("patient_chunks")

# collection.delete_many({})
# ─────────────────────────────────────────
# 2️⃣ MRN Cleaner
# ─────────────────────────────────────────

def clean_mrn(mrn) -> str:
    cleaned = (
        str(mrn)
        .upper()
        .replace("MRN", "")
        .replace("MRD", "")
        .replace("#",   "")
        .replace(" ",   "")
        .replace(":",   "")
        .replace("-",   "")
        .strip()
    )
    return f"MRN{cleaned.zfill(3)}"


# ─────────────────────────────────────────
# 3️⃣ Section Headers
# ─────────────────────────────────────────

SECTION_HEADERS = [
    "CHIEF COMPLAINT",
    "CHIEF COMPLAINTS AND PROGRESS",
    "CHIEF COMPLAINTS",
    "HISTORY OF PRESENT ILLNESS",
    "PAST MEDICAL HISTORY",
    "PREVIOUS MEDICAL / SURGICAL HISTORY",
    "PREVIOUS MEDICAL SURGICAL HISTORY",
    "PHYSICAL EXAMINATION",
    "CLINICAL EXAMINATION ON ADMISSION",
    "INVESTIGATIONS",
    "RELEVANT INVESTIGATIONS",
    "COURSE IN THE HOSPITAL",
    "MEDICATIONS DURING HOSPITALISATION",
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
    "GENERAL INSTRUCTIONS",
]


# ─────────────────────────────────────────
# 4️⃣ Section-Based Chunking  ← FIX 6
# ─────────────────────────────────────────

def split_by_sections(text: str):
    """
    Splits medical document into section-aware chunks using ONLY known
    SECTION_HEADERS as split points. This prevents mid-section splits
    on sentences like "Menstrual history –" or "Obstetric history –"
    which are content, not headers.
    """

    if not text or not text.strip():
        return []

    # ── Step 1: Clean text ─────────────────────────────────────────────────
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.replace(" .", ".")
    text = text.strip()

    lines = text.split("\n")

    # ── Step 2: Walk lines, split ONLY on known SECTION_HEADERS ───────────
    # A line is a known header if its content (stripped of trailing colon/space)
    # exactly matches one of our SECTION_HEADERS (case-insensitive).
    chunks        = []
    current_lines = []
    current_head  = "HEADER"

    def is_known_header(line: str) -> str | None:
        """Return normalized header name if line is a known section header, else None."""
        candidate = line.strip().rstrip(":").strip().upper()
        # Allow trailing " :" variants and partial matches for known headers
        for h in SECTION_HEADERS:
            if candidate == h or candidate.startswith(h):
                return h
        return None

    for line in lines:
        header_match = is_known_header(line)
        if header_match:
            # Save previous chunk
            body = "\n".join(current_lines).strip()
            if body and len(body) > 30:
                chunks.append({"section": current_head, "text": body})
            current_head  = header_match
            current_lines = [line.strip()]   # keep header line in text too
        else:
            current_lines.append(line)

    # Save last chunk
    body = "\n".join(current_lines).strip()
    if body and len(body) > 30:
        chunks.append({"section": current_head, "text": body})

    # ── Step 3: Fallback — paragraph split if no known headers found ───────
    if not chunks:
        print("⚠️ No known section headers detected — using paragraph fallback")
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        for i, para in enumerate(paragraphs):
            chunks.append({"section": f"PARAGRAPH_{i}", "text": para})

    # ── Step 4: Final fallback ─────────────────────────────────────────────
    if not chunks:
        print("⚠️ Paragraph fallback failed — storing full document as one chunk")
        chunks = [{"section": "FULL_DOCUMENT", "text": text}]

    return chunks

# ─────────────────────────────────────────
# 5️⃣ Store Chunks
# ─────────────────────────────────────────

def store_chunks(mrn: str, raw_text: str):
    """
    Delete old embeddings for this MRN, re-chunk by section, embed, and store.
    Pass raw discharge summary text as `raw_text`.
    """
    mrn = clean_mrn(mrn)

    # ── Delete old chunks (safe — handle astrapy versions that lack .deleted_count)
    try:
        delete_result = collection.delete_many({"mrn": mrn})
        deleted_count = getattr(delete_result, "deleted_count", "?")
        print(f"🗑️ Deleted old chunks for {mrn}: {deleted_count} records")
    except Exception as e:
        print(f"⚠️ Could not delete old chunks for {mrn}: {e}")

    # ── Chunk the text (safe — fallback to whole-text chunk on any error)
    try:
        chunks = split_by_sections(raw_text)
    except Exception as e:
        print(f"⚠️ split_by_sections failed ({e}) — storing as single chunk")
        chunks = [{"section": "FULL_DOCUMENT", "text": raw_text.strip()}]

    if not chunks:
        print("⚠️ No chunks produced — storing as single chunk")
        chunks = [{"section": "FULL_DOCUMENT", "text": raw_text.strip()}]

    print(f"📦 Storing {len(chunks)} section-chunks for MRN: {mrn}")

    # ── Embed and insert each chunk
    for i, chunk in enumerate(chunks):
        try:
            embedding = generate_embedding(chunk["text"])
            collection.insert_one({
                "mrn":         mrn,
                "chunk_index": i,
                "section":     chunk["section"],
                "text":        chunk["text"],
                "$vector":     embedding
            })
        except Exception as e:
            print(f"⚠️ Failed to insert chunk {i} ({chunk['section']}): {e}")

    print(f"✅ Stored {len(chunks)} sections for {mrn}")


# ─────────────────────────────────────────
# 6️⃣ Relevant Section Extractor
# ─────────────────────────────────────────

STOPWORDS = {
    "what", "was", "the", "is", "did", "with", "for", "patient",
    "a", "an", "of", "in", "on", "to", "and", "or", "that",
    "this", "are", "were", "has", "have", "been", "at", "by"
}


def section_matches_question(section_name: str, question: str) -> bool:
    """
    Check if a section header is semantically related to the question.
    E.g. question "course in hospital" → matches "COURSE IN THE HOSPITAL"
    """
    q_words = set(re.sub(r'[^a-z ]', '', question.lower()).split()) - STOPWORDS
    s_words = set(re.sub(r'[^a-z ]', '', section_name.lower()).split()) - STOPWORDS
    return bool(q_words & s_words)


def extract_relevant_portion(text: str, question: str, max_lines: int = 60) -> str:
    """
    Return the FULL section text. Never filter out lines or truncate.
    Only strip completely blank lines at start/end.
    """
    lines = [l.strip() for l in text.split("\n")]
    # Remove leading/trailing blank lines only
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


# ─────────────────────────────────────────
# 7️⃣ Section Header Detector
# ─────────────────────────────────────────

def detect_target_section(question: str) -> str | None:
    """
    If the question directly names a known section header, return that header.
    E.g. "What is the course in the hospital?" → "COURSE IN THE HOSPITAL"
         "What were the investigations?"       → "RELEVANT INVESTIGATIONS"
         "Tell me the diagnosis"               → "DIAGNOSIS"
    Returns None if no section header is clearly referenced.
    """
    q_clean = re.sub(r'[^a-z /]', ' ', question.lower()).strip()
    q_words  = set(q_clean.split()) - STOPWORDS

    best_header  = None
    best_overlap = 0

    for header in SECTION_HEADERS:
        h_words  = set(re.sub(r'[^a-z /]', ' ', header.lower()).split()) - STOPWORDS
        if not h_words:
            continue
        overlap  = len(q_words & h_words)
        # Require overlap >= 2 words OR full header is a single meaningful word with overlap 1
        min_req  = 1 if len(h_words) == 1 else 2
        if overlap >= min_req and overlap > best_overlap:
            best_overlap = overlap
            best_header  = header

    return best_header


# ─────────────────────────────────────────
# 8️⃣ Vector Search (RAG)
# ─────────────────────────────────────────

def vector_search(question: str, mrn: str) -> dict:
    mrn = clean_mrn(mrn)

    # ── Step 1: Try direct section lookup first ────────────────────────────
    # If the question names a known section (e.g. "course in the hospital"),
    # fetch that chunk directly by section name — do NOT rely on embeddings.
    target_section = detect_target_section(question)

    if target_section:
        print(f"🎯 Direct section lookup: {target_section}")
        direct_results = list(collection.find(
            filter={"mrn": mrn, "section": target_section},
            limit=2,
            projection={"text": 1, "chunk_index": 1, "section": 1}
        ))

        if direct_results:
            parts = []
            for doc in direct_results:
                text = doc.get("text", "").strip()
                if len(text) > 20:
                    parts.append(f"[SECTION: {target_section}]\n{text}")

            if parts:
                sources = [
                    {
                        "chunk_index": doc.get("chunk_index", i),
                        "section":     doc.get("section", "Unknown"),
                        "preview":     doc["text"][:100] + "..."
                    }
                    for i, doc in enumerate(direct_results)
                ]
                return {
                    "answer":  "\n\n---\n\n".join(parts),
                    "sources": sources
                }

    # ── Step 2: Fallback to vector similarity search ───────────────────────
    print(f"🔍 Falling back to vector search for: {question}")
    query_vector = generate_embedding(question)

    results = list(collection.find(
        filter={"mrn": mrn},
        sort={"$vector": query_vector},
        limit=6,
        projection={"text": 1, "chunk_index": 1, "section": 1}
    ))

    if not results:
        return {"answer": "No relevant medical information found.", "sources": []}

    # Re-rank: sections whose name overlaps question words float to top
    q_words = set(re.sub(r'[^a-z ]', '', question.lower()).split()) - STOPWORDS

    def relevance_key(doc):
        sec      = doc.get("section", "").lower()
        sec_words = set(re.sub(r'[^a-z ]', '', sec).split())
        return -len(q_words & sec_words)

    results.sort(key=relevance_key)

    formatted_parts = []
    seen_sections   = set()

    for doc in results:
        text    = doc.get("text", "").strip()
        section = doc.get("section", "").strip()

        if len(text) < 20 or section in seen_sections:
            continue
        seen_sections.add(section)

        full_text = extract_relevant_portion(text, question)
        if full_text:
            formatted_parts.append(f"[SECTION: {section}]\n{full_text}")

    answer = "\n\n---\n\n".join(formatted_parts) if formatted_parts else "No specific information found."

    sources = [
        {
            "chunk_index": doc.get("chunk_index", i),
            "section":     doc.get("section", "Unknown"),
            "preview":     doc["text"][:100] + "..."
        }
        for i, doc in enumerate(results)
    ]

    return {"answer": answer, "sources": sources}


# ─────────────────────────────────────────
# 8️⃣ Time-Based Summary
# ─────────────────────────────────────────

def time_based_summary(mrn: str, time_range: str = "Last 6 Months") -> dict:
    mrn = clean_mrn(mrn)

    results = list(collection.find(
        filter={"mrn": mrn},
        limit=5,
        projection={"text": 1, "chunk_index": 1, "section": 1}
    ))

    if not results:
        return {"summary": "No medical records found.", "time_range": time_range}

    results.sort(key=lambda x: x.get("chunk_index", 0))

    priority_sections = {
        "DIAGNOSIS", "DISCHARGE MEDICATIONS",
        "STATUS AT DISCHARGE", "FOLLOW-UP", "ADVICE ON DISCHARGE"
    }

    summary_parts = []
    for doc in results:
        section = doc.get("section", "").upper()
        text    = doc.get("text", "").strip()
        if section in priority_sections and text:
            summary_parts.append(f"**{section}**\n{text[:400]}")

    # Fallback if no priority sections found
    if not summary_parts:
        summary_parts = [doc["text"][:300] for doc in results]

    summary = "\n\n---\n\n".join(summary_parts)

    return {"summary": summary, "time_range": time_range}


# ─────────────────────────────────────────
# 9️⃣ Medication Safety Check
# ─────────────────────────────────────────

def medication_safety_check(mrn: str) -> dict:
    mrn          = clean_mrn(mrn)
    query_vector = generate_embedding("discharge medications prescriptions drugs dosage")

    results = list(collection.find(
        filter={"mrn": mrn},
        sort={"$vector": query_vector},
        limit=3,
        projection={"text": 1, "section": 1}
    ))

    if not results:
        return {
            "medications_raw":     "No medications found.",
            "interactions_raw":    "No data.",
            "context_chunks_used": 0
        }

    # Prefer DISCHARGE MEDICATIONS section specifically
    med_chunks = [
        doc for doc in results
        if "MEDICATION" in doc.get("section", "").upper()
    ]

    # Fallback to all results if section not found
    if not med_chunks:
        med_chunks = results

    medications = "\n\n".join(
        doc["text"].strip()
        for doc in med_chunks
        if len(doc.get("text", "").strip()) > 20
    )

    return {
        "medications_raw":     medications,
        "interactions_raw":    "⚠️ Interaction check pending — will be performed by Nova Lite in API layer.",
        "context_chunks_used": len(med_chunks)
    }