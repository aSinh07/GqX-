GqX — Architecture and High-level Contracts

Goal

- GqX is a cross-platform RAG-enabled chat assistant UI/UX connected to real-time LLMs (Gemini, Olama, OpenAI etc.).

Components

1. Backend (FastAPI, Python)
   - Responsibilities: Provider adapters for LLMs, RAG (vector store), file ingestion, authentication, and serving REST/WS endpoints.
   - Key endpoints: /health, /chat (POST), /upload (POST), /rag/index (POST), /rag/search (POST).
   - Env vars: GEMINI_API_KEY, OLAMA_URL, OPENAI_API_KEY, VECTOR_STORE_DIR, DATABASE_URL.

2. Frontend (React + Vite)
   - Responsibilities: Chat UI (message list, composer), date/time header, camera/gallery upload, voice-to-text, settings for provider selection.
   - Connects to backend over HTTPS + WebSocket for streaming.

3. Vector store / RAG
   - Example options: Chroma, FAISS, Milvus. The skeleton uses a pluggable interface; example code will show local Chromadb or sentence-transformers embeddings.

4. Mobile clients
   - Minimal SwiftUI (iOS) and .NET MAUI (C#) stubs that call backend endpoints and demonstrate camera/mic usage.

Contracts

- Chat message shape (JSON):
  {
    "messages": [{"role": "user|assistant|system", "content": "..."}],
    "provider": "gemini|olama|openai",
    "stream": false
  }

- Chat response: {"reply":"...", "meta":{...}}

Notes & Next steps

- This repo contains starter skeletons and provider adapters with clear TODOs where provider-specific streaming authentication is required.
- You must obtain API keys for Gemini/OpenAI or run Olama locally. Replace placeholders in backend/.env.example.

Security and Licensing

- Third-party LLMs have their own ToS. Ensure you review them before commercial deployment.
- The code will be released under MIT for easy ownership transfer; confirm the license file.
