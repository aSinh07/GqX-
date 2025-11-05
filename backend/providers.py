import os
import httpx
import json
try:
    import google.auth
    from google.auth.transport.requests import Request as GoogleAuthRequest
except Exception:
    google = None

class BaseProvider:
    async def send_messages(self, messages):
        raise NotImplementedError()

    async def send_messages_stream(self, messages):
        """Async generator fallback: yield chunks of the full reply.

        Providers that support streaming can override this to yield tokens/chunks.
        """
        reply = await self.send_messages(messages)
        # yield in small chunks so client can stream
        chunk_size = 64
        for i in range(0, len(reply), chunk_size):
            yield reply[i:i+chunk_size]

class GeminiProvider(BaseProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        # Optional override endpoint (useful if Google changes API path)
        self.endpoint = os.environ.get('GEMINI_API_ENDPOINT')

    async def send_messages(self, messages):
        # Cloud-first: prefer Google ADC (service-account). Fall back to API key if provided.
        endpoint = self.endpoint or os.environ.get('GEMINI_API_ENDPOINT') or 'https://generativelanguage.googleapis.com/v1beta2/models/text-bison-001:generate'
        params = {}
        headers = {'Content-Type': 'application/json'}

        # Try Application Default Credentials first (service account)
        auth_used = None
        if google is not None:
            try:
                creds, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                creds.refresh(GoogleAuthRequest())
                token = creds.token
                headers['Authorization'] = f"Bearer {token}"
                auth_used = 'adc'
            except Exception:
                auth_used = None

        # If ADC not available, try API key
        if auth_used is None and self.api_key:
            params['key'] = self.api_key
            auth_used = 'api_key'

        if auth_used is None:
            return "(gemini) no credentials available; set GOOGLE_APPLICATION_CREDENTIALS or GEMINI_API_KEY"

        # Construct a simple request body. Replace/extend with official model schema for production.
        body = {"prompt": messages[-1]['content']}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(endpoint, json=body, params=params, headers=headers)
                if resp.status_code == 200:
                    try:
                        j = resp.json()
                    except Exception:
                        return resp.text
                    # Handle a few expected shapes
                    if isinstance(j, dict):
                        if 'candidates' in j and isinstance(j['candidates'], list) and len(j['candidates'])>0:
                            c = j['candidates'][0]
                            return c.get('output') or c.get('content') or c.get('text') or str(c)
                        if 'output' in j:
                            out = j['output']
                            if isinstance(out, dict):
                                return out.get('text') or str(out)
                            return str(out)
                        if 'result' in j:
                            return str(j['result'])
                        if 'text' in j:
                            return str(j['text'])
                    return str(j)
                else:
                    return f"(gemini) HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                return f"(gemini) request failed: {e}"

    async def send_messages_stream(self, messages):
        """Attempt to stream response from Gemini / Generative API using HTTP streaming.

        Falls back to BaseProvider.send_messages behavior if the endpoint doesn't stream.
        """
        endpoint = self.endpoint or os.environ.get('GEMINI_API_ENDPOINT') or 'https://generativelanguage.googleapis.com/v1beta2/models/text-bison-001:generate'
        params = {}
        headers = {'Content-Type': 'application/json'}

        # Prefer ADC
        auth_used = None
        if google is not None:
            try:
                creds, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                creds.refresh(GoogleAuthRequest())
                token = creds.token
                headers['Authorization'] = f"Bearer {token}"
                auth_used = 'adc'
            except Exception:
                auth_used = None

        if auth_used is None and self.api_key:
            params['key'] = self.api_key
            auth_used = 'api_key'

        body = {"prompt": messages[-1]['content']}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream('POST', endpoint, json=body, params=params, headers=headers) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        yield f"(gemini) HTTP {resp.status_code}: {text.decode('utf-8', errors='ignore')}"
                        return

                    # Try to stream text chunks as they arrive
                    try:
                        async for chunk in resp.aiter_text(chunk_size=256):
                            if chunk:
                                yield chunk
                        return
                    except Exception:
                        # If aiter_text isn't supported or no streaming, fall back
                        full = await resp.aread()
                        yield full.decode('utf-8', errors='ignore')
                        return
            except Exception as e:
                # On failure, fallback to non-streaming reply
                reply = await self.send_messages(messages)
                # yield reply in chunks
                for i in range(0, len(reply), 128):
                    yield reply[i:i+128]
                return

class OlamaProvider(BaseProvider):
    def __init__(self, url=None):
        self.url = url or os.environ.get('OLAMA_URL')

    async def send_messages(self, messages):
        # Olama: if you run a local model server, call it here.
        if not self.url:
            return "(olama) olama URL not configured"
        # Placeholder: echo
        return "(olama) Placeholder reply to: " + messages[-1]['content']

class OpenAIProvider(BaseProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')

    async def send_messages(self, messages):
        if not self.api_key:
            return "(openai) API key not set"
        # Minimal placeholder — implement GPT calls with official client or httpx
        return "(openai) Placeholder reply to: " + messages[-1]['content']

PROVIDERS = {
    'gemini': GeminiProvider,
    'olama': OlamaProvider,
    'openai': OpenAIProvider,
}

def get_provider(name: str):
    cls = PROVIDERS.get(name.lower())
    if not cls:
        return None
    return cls()
