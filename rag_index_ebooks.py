#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from sentence_transformers import SentenceTransformer

# Ścieżki
INPUT_DIR = Path("/mnt/vault/ebooki_txt/cleaned")
INDEX_DIR = Path("/mnt/vault/rag_index")
EMBEDS_PATH = INDEX_DIR / "embeddings.npy"
META_PATH = INDEX_DIR / "metadata.json"

# Model embeddingowy (musi być taki sam tutaj i w serwerze RAG)
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Chunkowanie
CHUNK_SIZE = 1200   # znaków
OVERLAP = 200       # znaków


def load_existing_index():
    """Wczytaj istniejące embeddingi i metadane, jeśli są."""
    if EMBEDS_PATH.exists() and META_PATH.exists():
        print(f"Loading existing index from {INDEX_DIR}")
        embeddings = np.load(EMBEDS_PATH)
        with open(META_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return embeddings, metadata
    else:
        print("No existing index found, starting fresh")
        return None, []


def save_index(embeddings: np.ndarray, metadata: List[Dict[str, Any]]):
    """Zapisz embeddingi i metadane."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDS_PATH, embeddings)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Index saved to {INDEX_DIR}")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[str]:
    """Proste chunkowanie po znakach z overlappem."""
    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap

    return chunks


def main():
    parser = argparse.ArgumentParser(
        description="Build or update embedding index from cleaned ebooks."
    )
    parser.add_argument(
        "--model",
        default=EMBED_MODEL_NAME,
        help="Sentence-transformers model name"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help="Characters per chunk"
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=OVERLAP,
        help="Characters overlap between chunks"
    )
    args = parser.parse_args()

    if not INPUT_DIR.exists():
        print(f"Input directory does not exist: {INPUT_DIR}")
        return

    # Wczytaj istniejący indeks (jeśli jest)
    existing_embeds, metadata = load_existing_index()

    # Które pliki już są w indeksie?
    indexed_files = {
        m["book_path"] for m in metadata if "book_path" in m
    }

    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {INPUT_DIR}")
        return

    print(f"Found {len(txt_files)} cleaned text files")

    model = SentenceTransformer(args.model)
    all_new_embeddings = []
    all_new_meta = []

    for book_path in txt_files:
        book_str = str(book_path)

        if book_str in indexed_files:
            print(f"Skipping already indexed: {book_path.name}")
            continue

        print(f"\nIndexing: {book_path.name}")
        try:
            with open(book_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            print(f"Error reading {book_path}: {e}")
            continue

        if not text.strip():
            print("File is empty, skipping")
            continue

        chunks = chunk_text(text, chunk_size=args.chunk_size, overlap=args.overlap)
        print(f"Chunked into {len(chunks)} chunks")

        # Oblicz embeddingi dla wszystkich chunków tej książki
        try:
            embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=True)
        except Exception as e:
            print(f"Error encoding {book_path}: {e}")
            continue

        # Zbuduj metadane
        for i, chunk in enumerate(chunks):
            all_new_meta.append({
                "book_path": book_str,
                "book_name": book_path.name,
                "chunk_index": i,
                "text": chunk,
            })

        all_new_embeddings.append(embeddings)

    # Jeśli nie ma nowych danych – wyjdź
    if not all_new_meta:
        print("\nNo new books to index.")
        return

    # Sklej embeddingi
    new_embeds = np.vstack(all_new_embeddings)

    if existing_embeds is not None and len(metadata) > 0:
        print("\nMerging with existing index...")
        merged_embeds = np.vstack([existing_embeds, new_embeds])
        merged_meta = metadata + all_new_meta
    else:
        merged_embeds = new_embeds
        merged_meta = all_new_meta

    save_index(merged_embeds, merged_meta)
    print(f"\nIndexed {len(all_new_meta)} chunks "
          f"from {len({m['book_path'] for m in all_new_meta})} new books.")


if __name__ == "__main__":
    main()