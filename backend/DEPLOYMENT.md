GqX Backend — Deployment & Gemini setup

This document explains how to configure a cloud-first deployment and wire up Gemini (Google Generative Models).

1) Gemini API keys / credentials
   - Google Cloud's Generative models typically require authentication using a Google Cloud service account (recommended) or an API key for some endpoints.
   - Recommended: create a service account with the Cloud AI Platform / Generative AI permissions, then download the JSON key and set the environment variable:

       GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json

   - If you have an API key you can set:

       GEMINI_API_KEY=your_api_key

     and optionally override the endpoint:

       GEMINI_API_ENDPOINT=https://generativelanguage.googleapis.com/v1beta2/models/YOUR_MODEL:generate

   - Note: the `GeminiProvider` in `backend/providers.py` contains a best-effort scaffold. For production you should use the official Google client libraries (`google-cloud-aiplatform`) and service account auth.

2) Environment variables
   - Copy `.env.example` to `.env` and set keys:

       GEMINI_API_KEY=
       OPENAI_API_KEY=
       OLAMA_URL=
       VECTOR_STORE_DIR=./vector_store
       UPLOAD_DIR=./uploads

   - For Google service-account-based auth set `GOOGLE_APPLICATION_CREDENTIALS` as above.

3) Vector DB (RAG)
   - This starter uses Chromadb locally via `backend/rag_indexer.py` for indexing and searching. For scale switch to Pinecone / Milvus / Weaviate.

4) Docker / hosting
   - Example: create a Dockerfile for the backend, mount the `.env` and persistent storage for uploads / vector db.

5) Security & production notes
   - Never check API keys into source control.
   - Add authentication (JWT/OAuth) in front of the chat endpoint before launching publicly.
   - Add rate limiting and usage billing for API costs.
