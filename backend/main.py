import os
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles
from providers import get_provider
from rag_indexer import query as rag_query
from auth import create_tenant, verify_api_key
from vector_store import upsert_documents, enqueue_documents
import asyncio
import aioredis
from auth_db import init_db as init_auth_db
import time
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI(title="GqX Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event('startup')
async def startup_event():
    # initialize DB auth if configured
    if os.environ.get('USE_DB_AUTH','').lower() in ('1','true','yes'):
        try:
            await init_auth_db()
        except Exception:
            pass
    # init redis if available
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            app.state.redis = await aioredis.from_url(redis_url)
        except Exception:
            app.state.redis = None


@app.on_event('shutdown')
async def shutdown_event():
    r = getattr(app.state, 'redis', None)
    if r:
        try:
            await r.close()
        except Exception:
            pass

class ChatRequest(BaseModel):
    messages: list
    provider: str = "gemini"
    stream: bool = False
    rag: bool = True


def get_tenant_from_header(authorization: str = Header(None)):
    # expecting header: Authorization: Bearer <api_key>
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Invalid Authorization header')
    api_key = parts[1]
    tid = verify_api_key(api_key)
    if not tid:
        raise HTTPException(status_code=403, detail='Invalid API key')
    return tid

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.post("/chat")
async def chat(req: ChatRequest, tenant_id: str = Depends(get_tenant_from_header), request: Request = None):
    provider = get_provider(req.provider)
    if provider is None:
        raise HTTPException(status_code=400, detail="Unknown provider")

    # Optionally run RAG retrieval and prepend as a system message
    try:
        rag_enabled = req.rag if hasattr(req, 'rag') else (os.environ.get('RAG_ENABLED', 'true').lower() == 'true')
    except Exception:
        rag_enabled = True

    messages_to_send = list(req.messages)
    if rag_enabled:
        # Find last user content to query the vector DB
        last_user = None
        for m in reversed(req.messages):
            if isinstance(m, dict) and m.get('role') == 'user':
                last_user = m.get('content')
                break
        if last_user:
            try:
                docs = rag_query(last_user, k=3)
                if docs:
                    # Concatenate retrieved documents into a system prompt
                    retrieved_texts = "\n\n".join([d.get('document','') for d in docs])
                    system_msg = {"role": "system", "content": f"Relevant documents:\n{retrieved_texts}"}
                    messages_to_send.insert(0, system_msg)
            except Exception:
                # If RAG fails, continue without RAG
                pass

    # Call provider and return a text reply (sync for now)
    # Simple quota check (per-minute)
    try:
        redis = request.app.state.redis
        key = f"quota:{tenant_id}:{int(time.time()//60)}"
        cur = await redis.incr(key)
        if cur == 1:
            await redis.expire(key, 61)
        max_per_min = int(os.environ.get('MAX_REQS_PER_MIN', '600'))
        if cur > max_per_min:
            raise HTTPException(status_code=429, detail='Rate limit exceeded')
    except AttributeError:
        # redis not configured — allow
        pass

    reply = await provider.send_messages(messages_to_send)
    return {"reply": reply}


@app.post('/tenant/create')
async def tenant_create(name: str):
    info = create_tenant(name)
    return info


@app.post('/upload/index')
async def upload_and_index(file: UploadFile = File(...), tenant_id: str = Depends(get_tenant_from_header)):
    # Saves file and indexes it into vector store for the tenant.
    filename = os.path.basename(file.filename)
    path = os.path.join(UPLOAD_DIR, filename)
    try:
        async with aiofiles.open(path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # naive text extraction for demo: store raw bytes decoded
    try:
        text = content.decode('utf-8', errors='ignore')
    except Exception:
        text = filename

    upsert_documents([text], ids=[filename], tenant_id=tenant_id)
    return {"filename": filename, "path": path}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, tenant_id: str = Depends(get_tenant_from_header), request: Request = None):
    provider = get_provider(req.provider)
    if provider is None:
        raise HTTPException(status_code=400, detail="Unknown provider")

    try:
        rag_enabled = req.rag if hasattr(req, 'rag') else (os.environ.get('RAG_ENABLED', 'true').lower() == 'true')
    except Exception:
        rag_enabled = True

    messages_to_send = list(req.messages)
    if rag_enabled:
        last_user = None
        for m in reversed(req.messages):
            if isinstance(m, dict) and m.get('role') == 'user':
                last_user = m.get('content')
                break
        if last_user:
            try:
                docs = rag_query(last_user, k=3)
                if docs:
                    retrieved_texts = "\n\n".join([d.get('document','') for d in docs])
                    system_msg = {"role": "system", "content": f"Relevant documents:\n{retrieved_texts}"}
                    messages_to_send.insert(0, system_msg)
            except Exception:
                pass

    # Simple quota check (per-minute)
    try:
        redis = request.app.state.redis
        key = f"quota:{tenant_id}:{int(time.time()//60)}"
        cur = await redis.incr(key)
        if cur == 1:
            await redis.expire(key, 61)
        max_per_min = int(os.environ.get('MAX_REQS_PER_MIN', '600'))
        if cur > max_per_min:
            raise HTTPException(status_code=429, detail='Rate limit exceeded')
    except AttributeError:
        # redis not configured — allow
        pass

    # Use provider's async generator if available
    async def event_stream():
        try:
            agen = provider.send_messages_stream(messages_to_send)
            async for chunk in agen:
                # ensure chunk is bytes
                if isinstance(chunk, str):
                    chunk = chunk.encode('utf-8')
                yield chunk
                await asyncio.sleep(0)
        except Exception as e:
            err = f"(stream-error) {e}".encode('utf-8')
            yield err

    return StreamingResponse(event_stream(), media_type='text/plain; charset=utf-8')

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    filename = os.path.basename(file.filename)
    path = os.path.join(UPLOAD_DIR, filename)
    try:
        async with aiofiles.open(path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"filename": filename, "path": path}

# Simple run guard for uvicorn (used by dev)
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
