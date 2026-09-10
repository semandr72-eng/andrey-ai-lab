import json
import os
from typing import List, Tuple, Any

import faiss
import numpy as np


def load_index(index_path: str, meta_path: str) -> Tuple[faiss.IndexFlatL2, np.ndarray]:
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise RuntimeError(
            "FAISS index or metadata not found. "
            "Run `python backend/build_index.py` first to build the RAG index."
        )

    with open(index_path, "rb") as f:
        index = faiss.deserialize_index(np.frombuffer(f.read(), dtype=np.uint8))
    metadata = np.load(meta_path, allow_pickle=True)
    return index, metadata


def search_similar(
    index: faiss.IndexFlatL2,
    metadata: np.ndarray,
    query_vec: np.ndarray,
    k: int = 3,
) -> List[Any]:
    distances, indices = index.search(query_vec, k)
    idxs = indices[0]
    results = []
    for i in idxs:
        if 0 <= i < len(metadata):
            results.append(metadata[i])
    return results


def load_faq_data(path: str):
    """Загружает FAQ данные из JSON файла."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


