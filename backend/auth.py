"""Simple tenant & API-key management.

This is a minimal implementation for prototyping. For production, move to a secure database
and use proper secret storage + rotation.
"""
import os
from typing import Optional

# This module provides a simple file-based tenant store for quick prototyping.
# If DATABASE_URL is set, prefer the DB-backed auth in `auth_db.py`.
USE_DB = bool(os.environ.get('USE_DB_AUTH', '').lower() in ('1','true','yes'))
if USE_DB:
    try:
        from .auth_db import create_tenant as create_tenant_db, verify_api_key as verify_api_key_db, issue_jwt
    except Exception:
        create_tenant_db = None
        verify_api_key_db = None

if not USE_DB:
    import json
    import secrets
    import hashlib
    TENANTS_FILE = os.environ.get('TENANTS_FILE', './tenants.json')

    def _load_tenants():
        if not os.path.exists(TENANTS_FILE):
            return {}
        with open(TENANTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_tenants(data):
        with open(TENANTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def create_tenant(name: str):
        data = _load_tenants()
        tenant_id = secrets.token_hex(8)
        api_key = secrets.token_urlsafe(32)
        # store hashed key
        h = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        data[tenant_id] = {'name': name, 'api_key_hash': h}
        _save_tenants(data)
        return {'tenant_id': tenant_id, 'api_key': api_key}

    def verify_api_key(api_key: str) -> Optional[str]:
        """Return tenant_id if api_key is valid, else None."""
        data = _load_tenants()
        h = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        for tid, info in data.items():
            if info.get('api_key_hash') == h:
                return tid
        return None

