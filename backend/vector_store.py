"""Vector store abstraction: Pinecone-first, Chromadb fallback.

This module provides simple `upsert_documents` and `query` helpers that are tenant-aware.
Set environment variables `PINECONE_API_KEY` and `PINECONE_ENV` to enable Pinecone.
Otherwise it will fall back to the local Chromadb implementation provided earlier.
"""
import os
from typing import List, Optional

PINECONE_KEY = os.environ.get('PINECONE_API_KEY')
PINECONE_ENV = os.environ.get('PINECONE_ENV')
COLLECTION_NAME = os.environ.get('VECTOR_COLLECTION', 'gqx_collection')

_use_pinecone = bool(PINECONE_KEY and PINECONE_ENV)

if _use_pinecone:
    try:
        import pinecone
        pinecone.init(api_key=PINECONE_KEY, environment=PINECONE_ENV)
    except Exception:
        _use_pinecone = False

if not _use_pinecone:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        _chroma_client = chromadb.Client()
        _embedder = SentenceTransformer(os.environ.get('EMBEDDING_MODEL','all-MiniLM-L6-v2'))
    except Exception:
        _chroma_client = None
        _embedder = None


def upsert_documents(texts: List[str], ids: Optional[List[str]] = None, tenant_id: Optional[str] = None):
    """Insert documents into chosen vector store. Attach tenant_id to metadata.

    Returns dict with summary.
    """
    if ids is None:
        ids = [f"doc_{i}" for i in range(len(texts))]

    metadatas = [{"tenant_id": tenant_id} for _ in texts]

    if _use_pinecone:
        # create index if missing
        idx_name = COLLECTION_NAME
        if idx_name not in pinecone.list_indexes():
            pinecone.create_index(idx_name, dimension=384)  # dimension placeholder
        idx = pinecone.Index(idx_name)
        # embeddings: use sentence-transformers for now
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer(os.environ.get('EMBEDDING_MODEL','all-MiniLM-L6-v2'))
        vectors = embedder.encode(texts).tolist()
        to_upsert = [(ids[i], vectors[i], metadatas[i]) for i in range(len(ids))]
    idx.upsert(to_upsert)
    return {"upserted": len(ids), "provider": "pinecone"}

    # fallback to chroma
    if _chroma_client is None or _embedder is None:
        raise RuntimeError('No vector store available (pinecone not configured and chroma not available)')
    try:
        collection = _chroma_client.get_collection(COLLECTION_NAME)
    except Exception:
        collection = _chroma_client.create_collection(COLLECTION_NAME)

    embeddings = _embedder.encode(texts, show_progress_bar=False)
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings.tolist() if hasattr(embeddings,'tolist') else embeddings)
    return {"upserted": len(ids), "provider": "chromadb"}


def enqueue_documents(texts: List[str], ids: Optional[List[str]] = None, tenant_id: Optional[str] = None):
    """Enqueue documents into Redis index queue for background processing.

    Falls back to immediate upsert if Redis is not configured.
    """
    REDIS_URL = os.environ.get('REDIS_URL')
    task = {'texts': texts, 'ids': ids or [f"doc_{i}" for i in range(len(texts))], 'tenant_id': tenant_id}
    if not REDIS_URL:
        return upsert_documents(texts, ids=ids, tenant_id=tenant_id)
    import aioredis, asyncio, json

    async def _push():
        r = await aioredis.from_url(REDIS_URL)
        await r.rpush('index_queue', json.dumps(task))

    # schedule and return
    try:
        asyncio.create_task(_push())
        return {'enqueued': len(task['ids'])}
    except Exception:
        # if we can't schedule, fall back to synchronous
        return upsert_documents(texts, ids=ids, tenant_id=tenant_id)


def query(text: str, k: int = 3, tenant_id: Optional[str] = None):
    """Query top-k documents; if tenant_id provided, filter by metadata if supported.

    Returns list of dicts: {'id','document','metadata','score'}
    """
    if _use_pinecone:
        idx_name = COLLECTION_NAME
        if idx_name not in pinecone.list_indexes():
            return []
        idx = pinecone.Index(idx_name)
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer(os.environ.get('EMBEDDING_MODEL','all-MiniLM-L6-v2'))
        qv = embedder.encode([text])[0].tolist()
        res = idx.query(queries=[qv], top_k=k, include_metadata=True, include_values=False)
        out = []
        for match in res['results'][0]['matches']:
            md = match.get('metadata', {})
            if tenant_id and md.get('tenant_id') != tenant_id:
                continue
            out.append({'id': match['id'], 'document': md.get('text') or '', 'metadata': md, 'score': match.get('score')})
        return out

    if _chroma_client is None or _embedder is None:
        return []
    q_embed = _embedder.encode([text])
    results = _chroma_client.get_collection(COLLECTION_NAME).query(query_embeddings=q_embed.tolist() if hasattr(q_embed,'tolist') else q_embed, n_results=k, include=['documents','metadatas','distances'])
    out = []
    docs = results.get('documents', [])
    metas = results.get('metadatas', [])
    dists = results.get('distances', [])
    for docs_row, metas_row, dists_row in zip(docs, metas, dists):
        for doc, meta, dist in zip(docs_row, metas_row, dists_row):
            if tenant_id and meta.get('tenant_id') != tenant_id:
                continue
            out.append({'document': doc, 'metadata': meta, 'distance': dist})
    return out
