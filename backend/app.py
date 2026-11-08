import os
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import faiss

from .gigachat_client import create_client
from .embeddings import embed_texts
from .rag_index import load_index, search_similar


load_dotenv()

client = create_client()
if not client:
    raise RuntimeError(
        "GigaChat не настроен. Задайте GIGACHAT_CREDENTIALS "
        "или GIGACHAT_CLIENT_ID/GIGACHAT_CLIENT_SECRET в .env."
    )

app = FastAPI(title="FAQ RAG Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    top_k: int = 3


class ChatResponse(BaseModel):
    answer: str
    context: List[Dict[str, Any]]


INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "faiss_index.bin")
META_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "faqs_metadata.npy")

faiss_index, metadata = load_index(INDEX_PATH, META_PATH)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty")

    query_vec = embed_texts([req.message])
    similar_items = search_similar(faiss_index, metadata, query_vec, k=req.top_k)

    context_text = "\n\n".join(
        [f"Q: {item['question']}\nA: {item['answer']}" for item in similar_items]
    )

    system_prompt = (
        "Ты FAQ-ассистент компании. Отвечай кратко и по делу на русском языке. "
        "Используй предоставленный контекст с вопросами и ответами. "
        "Если в контексте нет нужной информации, скажи, что не уверен и предложи связаться с поддержкой."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Вопрос пользователя: {req.message}\n\nКонтекст FAQ:\n{context_text}"},
    ]

    completion = client.chat(
        {
            "messages": messages,
            "temperature": 0.2,
        }
    )

    answer = completion.choices[0].message.content

    return ChatResponse(answer=answer, context=similar_items)


@app.get("/health")
async def health():
    return {"status": "ok"}


