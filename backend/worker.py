"""Background worker for async indexing tasks.

This simple worker connects to Redis LIST `index_queue` and processes items.
Each item is expected to be a JSON with fields: texts, ids, tenant_id.
"""
import os
import asyncio
import json
import logging
import aioredis
from vector_store import upsert_documents

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
logger = logging.getLogger('gqx.worker')

async def run_worker():
    redis = await aioredis.from_url(REDIS_URL)
    logger.info('Worker started, listening for index tasks')
    while True:
        try:
            item = await redis.blpop('index_queue', timeout=5)
            if not item:
                await asyncio.sleep(0.1)
                continue
            _, raw = item
            task = json.loads(raw)
            texts = task.get('texts')
            ids = task.get('ids')
            tenant_id = task.get('tenant_id')
            logger.info(f'Indexing {len(texts)} docs for tenant {tenant_id}')
            upsert_documents(texts, ids=ids, tenant_id=tenant_id)
        except Exception as e:
            logger.exception('Worker error: %s', e)
            await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(run_worker())
