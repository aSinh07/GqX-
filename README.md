GqX — RAG AI Chatbot

This repository contains a starter skeleton for GqX: a cross-platform RAG-enabled chat assistant. It includes:

- backend/ — FastAPI backend with provider adapters (placeholders)
- frontend/ — React + Vite web UI prototype
- mobile/ — minimal README stubs for iOS (Swift) and C# (.NET MAUI)
- ARCHITECTURE.md with design notes

Next steps

1. Fill in provider-specific implementations in `backend/providers.py` for Gemini/Olama/OpenAI.
2. Implement vector store and RAG indexing (Chroma, FAISS or Milvus).
3. Harden auth, rate-limiting, and privacy features before launch.

License: MIT (see LICENSE)
