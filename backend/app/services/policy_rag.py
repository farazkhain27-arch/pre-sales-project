"""
RAG pipeline over company internal policy documents.

Flow:
  upload -> extract_text -> chunk -> embed (Voyage AI) -> store PolicyChunk rows
  ask(question) -> embed(question) -> cosine-similarity top-K retrieval
                 -> Claude answers using ONLY the retrieved chunks as context

Design principle (same one used everywhere else in this product): retrieval
is deterministic (cosine similarity over real embeddings, not a model
guess), and the LLM is only allowed to answer from the retrieved text — it's
explicitly instructed to say so if the policy library doesn't cover the
question, so nobody mistakes a hallucination for actual company policy.
"""
import math
from typing import List
from sqlalchemy.orm import Session
import voyageai
from anthropic import Anthropic

from .. import models
from ..config import get_settings

settings = get_settings()

SIMILARITY_THRESHOLD = 0.35   # below this, we tell the user we don't have policy coverage


def _voyage_client() -> voyageai.Client:
    return voyageai.Client(api_key=settings.VOYAGE_API_KEY)


def _anthropic_client() -> Anthropic:
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """Simple sliding-window character chunking with overlap, on paragraph boundaries where possible."""
    chunk_size = chunk_size or settings.POLICY_CHUNK_SIZE
    overlap = overlap or settings.POLICY_CHUNK_OVERLAP
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # try to break on a paragraph/sentence boundary near the end
        if end < len(text):
            boundary = text.rfind("\n\n", start, end)
            if boundary == -1:
                boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end - overlap > start else end
    return chunks


def embed_texts(texts: List[str], input_type: str = "document") -> List[List[float]]:
    if not texts:
        return []
    client = _voyage_client()
    result = client.embed(texts, model=settings.EMBEDDING_MODEL, input_type=input_type)
    return result.embeddings


def ingest_policy_document(db: Session, policy_doc: models.PolicyDocument, raw_text: str) -> int:
    """Chunks + embeds a policy document's text and stores PolicyChunk rows. Returns chunk count."""
    chunks = chunk_text(raw_text)
    if not chunks:
        policy_doc.ingested = True
        policy_doc.chunk_count = 0
        db.commit()
        return 0

    embeddings = embed_texts(chunks, input_type="document")

    db.query(models.PolicyChunk).filter(
        models.PolicyChunk.document_id == policy_doc.id
    ).delete()

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        db.add(models.PolicyChunk(
            tenant_id=policy_doc.tenant_id,
            document_id=policy_doc.id,
            chunk_index=idx,
            content=chunk,
            embedding=embedding,
        ))

    policy_doc.ingested = True
    policy_doc.chunk_count = len(chunks)
    db.commit()
    return len(chunks)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_relevant_chunks(db: Session, tenant_id: str, query: str, top_k: int = None):
    """
    Deterministic retrieval: embed the query, cosine-similarity-rank every
    chunk belonging to this tenant, return the top K with scores.
    """
    top_k = top_k or settings.POLICY_TOP_K
    all_chunks = db.query(models.PolicyChunk).filter(
        models.PolicyChunk.tenant_id == tenant_id
    ).all()
    if not all_chunks:
        return []

    query_embedding = embed_texts([query], input_type="query")[0]

    scored = [
        (chunk, _cosine_similarity(query_embedding, chunk.embedding))
        for chunk in all_chunks
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


ANSWER_SYSTEM_PROMPT = """You are a company-policy assistant for a presales team. You will be given
excerpts retrieved from the company's internal policy documents, plus a question.

Rules:
- Answer ONLY using the provided excerpts. Do not use outside knowledge of general business practice.
- If the excerpts don't actually answer the question, say clearly that the policy library doesn't
  cover this and recommend the person check with sales ops / management — do not guess or infer
  a policy that isn't explicitly stated in the excerpts.
- Cite which excerpt(s) support each claim using [1], [2] etc. matching the excerpt numbers given.
- Be concise and direct — this is being read by a sales engineer preparing a bid, not a lawyer."""


def answer_policy_question(db: Session, tenant_id: str, question: str) -> dict:
    scored_chunks = retrieve_relevant_chunks(db, tenant_id, question)
    relevant = [(chunk, score) for chunk, score in scored_chunks if score >= SIMILARITY_THRESHOLD]

    if not relevant:
        return {
            "answer": "I couldn't find anything in the uploaded policy documents that covers this. "
                      "Please check with sales ops/management, or upload the relevant policy document.",
            "sources": [],
            "grounded": False,
        }

    context_blocks = []
    for i, (chunk, score) in enumerate(relevant, start=1):
        doc = chunk.document
        context_blocks.append(f"[{i}] (from '{doc.title}', section {chunk.chunk_index}):\n{chunk.content}")
    context_text = "\n\n".join(context_blocks)

    client = _anthropic_client()
    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1000,
        system=ANSWER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Policy excerpts:\n\n{context_text}\n\nQuestion: {question}"
        }],
    )
    answer_text = "".join(block.text for block in response.content if block.type == "text").strip()

    sources = [
        {
            "document_title": chunk.document.title,
            "chunk_index": chunk.chunk_index,
            "excerpt": chunk.content[:280] + ("..." if len(chunk.content) > 280 else ""),
            "similarity": round(score, 3),
        }
        for chunk, score in relevant
    ]

    return {"answer": answer_text, "sources": sources, "grounded": True}
