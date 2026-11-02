import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPBasic
from .db import db, one


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ':' + digest.hex()


def password_ok(password, stored):
    try:
        salt, digest = stored.split(':')
        return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                                                  n=16384, r=8, p=1).hex(), digest)
    except (ValueError, TypeError):
        return False


def fingerprint(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, credential=Depends(HTTPBearer(auto_error=False))):
    auth = request.headers.get('authorization', '')
    bearer = auth.startswith('Bearer ')
    token = auth[7:] if bearer else request.cookies.get('saldo_session', '')
    if not token:
        raise HTTPException(401, 'Inicia sesión', headers={'WWW-Authenticate': 'Bearer'})
    with db() as conn:
        user = one(conn, '''SELECT u.*, s.csrf FROM sessions s JOIN users u ON u.id=s.user_id
                            WHERE token_hash=%s AND expires_at>now() AND u.active''', (fingerprint(token),))
    if not user or user['role'] == 'bi':
        raise HTTPException(401, 'Sesión inválida o vencida')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and not bearer:
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), user['csrf']):
            raise HTTPException(403, 'Falta protección CSRF')
    return user


def admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Solo administración')
    return user


def report_user(request: Request, bearer=Depends(HTTPBearer(auto_error=False)), basic=Depends(HTTPBasic(auto_error=False))):
    auth = request.headers.get('authorization', '')
    if not auth.startswith('Basic '):
        return current_user(request)
    if os.getenv('APP_ENV', 'local') != 'local' and request.url.scheme != 'https':
        raise HTTPException(400, 'Basic requiere HTTPS')
    try:
        username, password = base64.b64decode(auth[6:], validate=True).decode().split(':', 1)
    except (ValueError, UnicodeError):
        raise HTTPException(401, 'Credencial inválida', headers={'WWW-Authenticate': 'Basic realm="reportes"'})
    with db() as conn:
        user = one(conn, "SELECT * FROM users WHERE email=%s AND active AND role='bi'", (username.lower(),))
    if not user or not password_ok(password, user['password_hash']):
        raise HTTPException(401, 'Credencial inválida', headers={'WWW-Authenticate': 'Basic realm="reportes"'})
    return user
