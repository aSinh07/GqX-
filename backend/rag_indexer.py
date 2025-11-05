"""
Simple RAG indexer using Chromadb + sentence-transformers.

This is a lightweight helper to index texts (documents) locally and query them.

Usage:
  - pip install -r requirements.txt
  - from rag_indexer import index_texts, query
  - index_texts(["doc1 text", "doc2 text"], ids=["d1","d2"])  # one-time
  - results = query("search text", k=3)

Notes:
  - Chromadb must be installable in your environment. This example uses an in-process chromadb client.
  - For production use consider a hosted vector DB (Pinecone, Milvus, Weaviate) and batched indexing.
"""
from typing import List, Optional
import os
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
except Exception:
    chromadb = None

_MODEL_NAME = os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION', 'gqx_collection')

_client = None
_embedder = None

def _init():
    global _client, _embedder
    if chromadb is None:
        raise RuntimeError('chromadb or sentence-transformers not installed. See requirements.txt')
    if _client is None:
        # in-memory/temporary chroma; change settings for persistent store
        _client = chromadb.Client()
    if _embedder is None:
        _embedder = SentenceTransformer(_MODEL_NAME)

def index_texts(texts: List[str], ids: Optional[List[str]] = None, metadatas: Optional[List[dict]] = None):
    """Index a list of texts into Chroma.

    texts: list of strings
    ids: optional list of ids (strings). If None, auto-generated.
    metadatas: optional list of metadata dicts.
    """
    _init()
    collection = None
    try:
        collection = _client.get_collection(_COLLECTION_NAME)
    except Exception:
        collection = _client.create_collection(_COLLECTION_NAME)

    embeddings = _embedder.encode(texts, show_progress_bar=False)
    if ids is None:
        ids = [f"doc_{i}" for i in range(len(texts))]

    collection.add(ids=ids, documents=texts, metadatas=metadatas or [{} for _ in texts], embeddings=embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings)
    return {'added': len(texts)}

def query(query_text: str, k: int = 3):
    """Return top-k matching documents for query_text."""
    _init()
    try:
        collection = _client.get_collection(_COLLECTION_NAME)
    except Exception:
        return []

    q_embed = _embedder.encode([query_text])
    results = collection.query(query_embeddings=q_embed.tolist() if hasattr(q_embed, 'tolist') else q_embed, n_results=k, include=['documents','metadatas','distances'])
    # results is dict with keys; normalize for caller
    out = []
    for docs, metas, dists in zip(results.get('documents', []), results.get('metadatas', []), results.get('distances', [])):
        for doc, meta, dist in zip(docs, metas, dists):
            out.append({'document': doc, 'metadata': meta, 'distance': dist})
    return out

if __name__ == '__main__':
    print('RAG indexer helper. Call index_texts() and query() from your code.')
