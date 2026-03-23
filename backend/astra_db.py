from astrapy.client import DataAPIClient
from dotenv import load_dotenv
import os
import requests

load_dotenv()

ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
OLLAMA_BASE_URL = "http://localhost:11434"

# Connect to AstraDB
client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
db = client.get_database_by_api_endpoint(ASTRA_DB_API_ENDPOINT)
collection = db.get_collection("patient_chunks")


# ─────────────────────────────────────────
# MRN CLEANER
# ─────────────────────────────────────────
def clean_mrn(mrn) -> int:        # ← remove type hint str, accept anything
    cleaned = (
        str(mrn)                  # ← add this line, converts 8 → "8" first
        .upper()
        .replace("MRN", "")
        .replace("MRD", "")
        .replace("#", "")
        .replace(" ", "")
        .replace(":", "")
        .strip()
    )
    return int(cleaned)

# ─────────────────────────────────────────
# EMBEDDING
# ─────────────────────────────────────────
def generate_embedding(text: str) -> list:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    response.raise_for_status()
    return response.json()["embedding"]



# ─────────────────────────────────────────
# STORE CHUNKS
# ─────────────────────────────────────────
def store_chunks(mrn: str, chunks: list):
    mrn = clean_mrn(mrn)
    print(f"Storing {len(chunks)} chunks for MRN: '{mrn}'")
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        collection.insert_one({
            "mrn": mrn,
            "chunk_index": i,
            "text": chunk,
            "$vector": embedding
        })
    print(f"✅ Done storing for MRN: '{mrn}'")


# ─────────────────────────────────────────
# CALL LLM
# ─────────────────────────────────────────
def call_llm(system_instruction: str, context: str, question: str) -> str:
    prompt = f"""<|start_header_id|>system<|end_header_id|>
{system_instruction}
<|eot_id|>

<|start_header_id|>user<|end_header_id|>
MEDICAL RECORD:
\"\"\"
{context}
\"\"\"

QUESTION: {question}
<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>
"""
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "repeat_penalty": 1.2,
                "top_p": 0.85,
                "top_k": 40,
                "num_predict": 400,
                "stop": [
                    "<|eot_id|>",
                    "<|start_header_id|>",
                    "QUESTION:",
                    "MEDICAL RECORD:"
                ]
            }
        }
    )
    response.raise_for_status()
    answer = response.json()["response"].strip()
    return answer if answer and len(answer) > 5 else "Not mentioned in the record."


# ─────────────────────────────────────────
# TAB 1 — VECTOR SEARCH (Patient Query)
# ─────────────────────────────────────────
def vector_search(question: str, mrn: str) -> dict:
    mrn = clean_mrn(mrn)
    print(f"[vector_search] MRN='{mrn}' | Q='{question}'")

    # ADD THIS — check count before searching
    count = collection.count_documents(filter={"mrn": mrn}, upper_bound=100)
    print(f"Documents in DB for MRN {mrn}: {count}")

    if count == 0:
        return {
            "answer": f"No records found for MRN {mrn}. Please ingest the document first.",
            "sources": []
        }

    query_vector = generate_embedding(question)

    query_vector = generate_embedding(question)

    results = list(collection.find(
        filter={"mrn": mrn},
        sort={"$vector": query_vector},
        limit=12,
        projection={"text": 1, "chunk_index": 1}
    ))

    if not results:
        return {
            "answer": "No relevant medical information found for this patient.",
            "sources": []
        }

    results.sort(key=lambda x: x.get("chunk_index", 0))
    top_chunks = results[:7]

    context = "\n\n".join(
        f"[Chunk {i+1}]:\n{doc['text']}" for i, doc in enumerate(top_chunks)
    )

    system_instruction = """You are a strict clinical medical assistant.
- Answer ONLY using the medical record provided.
- Use information from: Chief Complaints, Previous Medical/Surgical History,
  Diagnosis, Clinical Examination, Course in Hospital, and Medications sections.
- If the answer is genuinely not present anywhere in the record, reply: "Not mentioned in the record."
- Be concise. Do NOT repeat the question or context."""

    answer = call_llm(system_instruction, context, question)

    sources = [
        {
            "chunk_index": doc.get("chunk_index", i),
            "preview": doc["text"][:120] + "..."
        }
        for i, doc in enumerate(top_chunks)
    ]

    return {"answer": answer, "sources": sources}


# ─────────────────────────────────────────
# TAB 2 — TIME-BASED SUMMARY
# ─────────────────────────────────────────
def time_based_summary(mrn: str, time_range: str = "Last 6 Months") -> dict:
    mrn = clean_mrn(mrn)
    print(f"[time_based_summary] MRN='{mrn}' | Range='{time_range}'")

    results = list(collection.find(
        filter={"mrn": mrn},
        limit=20,
        projection={"text": 1, "chunk_index": 1}
    ))

    if not results:
        return {
            "summary": "No medical records found for this patient.",
            "time_range": time_range
        }

    results.sort(key=lambda x: x.get("chunk_index", 0))
    context = "\n\n".join(
        f"[Chunk {i+1}]:\n{doc['text']}" for i, doc in enumerate(results)
    )

    system_instruction = f"""You are a clinical medical assistant generating a chronological patient summary.
- Summarize the patient's medical history for: {time_range}
- Structure your answer chronologically with key medical events.
- Include: diagnoses, treatments, medications, and outcomes.
- Do NOT invent information not present in the record.
- Format using bullet points by time period if dates are available."""

    summary = call_llm(
        system_instruction,
        context,
        f"Generate a chronological medical summary for the {time_range}."
    )
    return {"summary": summary, "time_range": time_range}


# ─────────────────────────────────────────
# TAB 3 — MEDICATION SAFETY
# ─────────────────────────────────────────
def medication_safety_check(mrn: str) -> dict:
    mrn = clean_mrn(mrn)
    print(f"[medication_safety_check] MRN='{mrn}'")

    query_vector = generate_embedding(
        "medications prescribed discharge drugs tablets injections"
    )

    results = list(collection.find(
        filter={"mrn": mrn},
        sort={"$vector": query_vector},
        limit=6,
        projection={"text": 1, "chunk_index": 1}
    ))

    if not results:
        return {
            "medications_raw": "No medication records found.",
            "interactions_raw": "No medication records found.",
            "context_chunks_used": 0
        }

    results.sort(key=lambda x: x.get("chunk_index", 0))
    context = "\n\n".join(
        f"[Chunk {i+1}]:\n{doc['text']}" for i, doc in enumerate(results)
    )

    med_system = """You are a clinical pharmacist assistant.
- Extract ONLY the medication names and dosages from the medical record.
- Return them as a numbered list. Example: 1. Amlodipine 5mg - once daily
- Include both hospital medications and discharge medications.
- If no medications found, say: "No medications found." """

    medications_raw = call_llm(
        med_system,
        context,
        "List all medications mentioned in this record with their dosages."
    )

    interaction_system = """You are a clinical pharmacist checking for drug-drug interactions.
- Based on the medications listed, identify any known interactions.
- For each: Drug A + Drug B → Risk level (Minor/Moderate/Major) → What to monitor.
- If no interactions, say: "No significant interactions detected." """

    interactions_raw = call_llm(
        interaction_system,
        f"Patient medications:\n{medications_raw}",
        "Check for drug-drug interactions among these medications."
    )

    return {
        "medications_raw": medications_raw,
        "interactions_raw": interactions_raw,
        "context_chunks_used": len(results)
    }


# ─────────────────────────────────────────
# DEBUG HELPER
# ─────────────────────────────────────────

def debug_pipeline(question: str, mrn: str):
    if __name__ == "__main__":
        debug_pipeline("red flag signs", "8")
    mrn_clean = clean_mrn(mrn)
    print(f"\n{'='*50}")
    print(f"DEBUG MRN='{mrn_clean}' | Q='{question}'")

    count = collection.count_documents(
        filter={"mrn": mrn_clean}, upper_bound=100
    )
    print(f"Chunks stored: {count}")

    if count == 0:
        print("❌ No documents found!")
        sample = collection.find({}, limit=3, projection={"mrn": 1})
        print("MRNs in DB:")
        for doc in sample:
            print(f"  - '{doc.get('mrn')}'")
        return

    query_vector = generate_embedding(question)
    results = list(collection.find(
        filter={"mrn": mrn_clean},
        sort={"$vector": query_vector},
        limit=5,
        projection={"text": 1, "chunk_index": 1}
    ))

    print(f"Vector search returned {len(results)} chunks")
    for i, doc in enumerate(results):
        print(f"\n--- Chunk {i+1} ---")
        print(doc["text"][:300])

    print(f"\n{'='*50}")
    print(" Pipeline OK")


