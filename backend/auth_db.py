"""Database-backed tenant management and JWT issuance.

Uses SQLAlchemy async engine with asyncpg. This is a minimal implementation for prototyping.
Environment variables:
  DATABASE_URL (e.g. postgresql+asyncpg://user:pass@host:5432/dbname)
  JWT_SECRET (secret key for signing tokens)

"""
import os
import secrets
import hashlib
import time
from typing import Optional
from passlib.context import CryptContext
import jwt
from sqlalchemy import Table, Column, String, MetaData, Boolean
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

DATABASE_URL = os.environ.get('DATABASE_URL')
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_urlsafe(32))
JWT_ALG = 'HS256'

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

metadata = MetaData()

tenants_table = Table(
    'tenants', metadata,
    Column('tenant_id', String, primary_key=True),
    Column('name', String, nullable=False),
    Column('api_key_hash', String, nullable=False),
    Column('created_at', String, nullable=False),
)

_engine: Optional[AsyncEngine] = None

def get_engine():
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError('DATABASE_URL not set for auth_db')
        _engine = create_async_engine(DATABASE_URL, echo=False)
    return _engine

async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

async def create_tenant(name: str):
    engine = get_engine()
    tenant_id = secrets.token_hex(8)
    api_key = secrets.token_urlsafe(32)
    api_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    now = str(int(time.time()))
    async with engine.begin() as conn:
        await conn.execute(tenants_table.insert().values(tenant_id=tenant_id, name=name, api_key_hash=api_hash, created_at=now))
    token = issue_jwt(tenant_id)
    return {'tenant_id': tenant_id, 'api_key': api_key, 'jwt': token}

async def verify_api_key(api_key: str) -> Optional[str]:
    engine = get_engine()
    h = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    async with engine.connect() as conn:
        q = select([tenants_table.c.tenant_id]).where(tenants_table.c.api_key_hash == h)
        r = await conn.execute(q)
        row = r.fetchone()
        if row:
            return row[0]
    return None

def issue_jwt(tenant_id: str, exp_seconds: int = 3600*24*7):
    payload = {'tid': tenant_id, 'iat': int(time.time()), 'exp': int(time.time()) + exp_seconds}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return token

def verify_jwt(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get('tid')
    except Exception:
        return None
