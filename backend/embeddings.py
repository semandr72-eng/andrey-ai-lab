"""Локальные эмбеддинги через fastembed (ONNX, данные не покидают сервер).

Модель paraphrase-multilingual-MiniLM-L12-v2 — мультиязычная, хорошо
работает с русским текстом. Если понадобится выше качество, можно заменить
на paraphrase-multilingual-mpnet-base-v2 (точнее, но ~420 МБ).
"""
from typing import List

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(MODEL_NAME)
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    vectors = list(_get_model().embed(texts))
    return np.array(vectors, dtype="float32")
