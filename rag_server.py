#!/usr/bin/env python3
from pathlib import Path
from typing import List, Dict, Any

import json
import numpy as np
import requests
from fastapi import FastAPI
from pydantic import BaseModel

from sentence_transformers import SentenceTransformer

# Ścieżki indeksu
INDEX_DIR = Path("/mnt/vault/rag_index")
EMBEDS_PATH = INDEX_DIR / "embeddings.npy"
META_PATH = INDEX_DIR / "metadata.json"

# Model embeddingowy – musi być ten sam, co w rag_index_ebooks.py
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Konfiguracja LLM (Bielik w Ollamie)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "SpeakLeash/bielik-1.5b-v3.0-instruct:Q8_0"


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class AskResponse(BaseModel):
    answer: str
    contexts: List[Dict[str, Any]]


app = FastAPI(title="Local RAG server", version="0.1.0")

# Ładowanie indeksu przy starcie
print(f"Loading index from {INDEX_DIR}...")
if not EMBEDS_PATH.exists() or not META_PATH.exists():
    raise RuntimeError("Index not found. Run rag_index_ebooks.py first.")

EMBEDS = np.load(EMBEDS_PATH)
with open(META_PATH, "r", encoding="utf-8") as f:
    METADATA = json.load(f)

print(f"Loaded {len(METADATA)} chunks with embeddings of shape {EMBEDS.shape}")

emb_model = SentenceTransformer(EMBED_MODEL_NAME)


def cosine_sim(query_vec: np.ndarray, db_vecs: np.ndarray) -> np.ndarray:
    """Prosty cosine similarity."""
    q = query_vec / np.linalg.norm(query_vec)
    d = db_vecs / np.linalg.norm(db_vecs, axis=1, keepdims=True)
    return d @ q


def retrieve_context(question: str, top_k: int) -> List[Dict[str, Any]]:
    """Znajdź top_k najbardziej pasujących chunków."""
    q_emb = emb_model.encode([question], convert_to_numpy=True)[0]
    sims = cosine_sim(q_emb, EMBEDS)
    idxs = sims.argsort()[-top_k:][::-1]

    results = []
    for idx in idxs:
        meta = METADATA[int(idx)]
        results.append({
            "book_path": meta.get("book_path"),
            "book_name": meta.get("book_name"),
            "chunk_index": meta.get("chunk_index"),
            "similarity": float(sims[int(idx)]),
            "text": meta.get("text"),
        })
    return results


def call_bielik(question: str, contexts: List[Dict[str, Any]]) -> str:
    """Zbuduj prompt z kontekstem i zapytaj Bielika przez Ollamę."""
    context_text = "\n\n---\n\n".join(
        f"[{c.get('book_name')} / chunk {c.get('chunk_index')}]:\n{c.get('text')}"
        for c in contexts
    )

    system_prompt = (
        "You are a helpful assistant for Kuba. "
        "You always answer in Polish, even if the question is in another language. "
        "You answer concisely and only based on the provided context when possible. "
        "If the context is insufficient, say that you cannot answer confidently."
    )

    user_prompt = (
        f"{system_prompt}\n\n"
        f"Kontekst z książek:\n"
        f"{context_text}\n\n"
        f"Pytanie użytkownika:\n{question}\n\n"
        f"Odpowiedz po polsku, wykorzystując głównie powyższy kontekst."
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_prompt,
        "stream": False,
    }

    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    # dla /api/generate odpowiedź jest w polu "response"
    answer = data.get("response", "").strip()
    return answer


@app.post("/ask", response_model=AskResponse)
def ask_rag(req: AskRequest):
    """Główne wejście RAG: pytanie → kontekst → Bielik → odpowiedź."""
    contexts = retrieve_context(req.question, req.top_k)
    answer = call_bielik(req.question, contexts)
    return AskResponse(answer=answer, contexts=contexts)