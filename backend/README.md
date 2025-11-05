GqX Backend

Quickstart

1. Create virtualenv and install dependencies:

   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

2. Copy .env.example to .env and fill keys.
3. Run:

   uvicorn main:app --reload --host 0.0.0.0 --port 8000

Notes

- Provider adapters in `providers.py` are placeholders. Implement provider-specific authentication and streaming calls there.
- Add vector store and RAG indexing scripts under `rag/` when ready.
