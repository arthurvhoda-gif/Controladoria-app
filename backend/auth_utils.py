"""Autenticação da Controladoria Haize. Segredos somente via variáveis de ambiente."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher, exceptions as argon_errors

ALGORITHM = 'HS256'
ISSUER = 'haize-controladoria-api'
AUDIENCE = 'haize-controladoria-app'
SESSION_HOURS = 8
hasher = PasswordHasher()


def get_secret():
    secret = os.getenv('AUTH_SECRET_KEY', '').strip()
    if len(secret) < 32:
        raise RuntimeError('AUTH_SECRET_KEY deve conter no mínimo 32 caracteres aleatórios.')
    return secret


def hash_password(password: str) -> str:
    if not password or len(password) < 10:
        raise ValueError('A senha deve ter pelo menos 10 caracteres.')
    return hasher.hash(password)


def verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """(é válida, precisa migrar hash legado)."""
    if not password or not stored:
        return False, False
    if stored.startswith('$argon2'):
        try:
            valid = hasher.verify(stored, password)
            return bool(valid), bool(valid and hasher.check_needs_rehash(stored))
        except (argon_errors.VerificationError, argon_errors.InvalidHashError):
            return False, False
    if stored.startswith(('$2a$', '$2b$', '$2y$')):
        try:
            import bcrypt
            return bool(bcrypt.checkpw(password.encode(), stored.encode())), True
        except Exception:
            return False, False
    if len(stored) == 64 and all(c in '0123456789abcdef' for c in stored.lower()):
        digest = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(digest, stored), True
    return hmac.compare_digest(password, stored), True


def _credential_version(password_hash: str) -> str:
    """Invalida JWT quando a senha armazenada é alterada."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:20]


def create_token(user) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user.id), 'iss': ISSUER, 'aud': AUDIENCE,
        'iat': now, 'nbf': now, 'exp': now + timedelta(hours=SESSION_HOURS),
        'pv': _credential_version(user.senha),
    }
    return jwt.encode(payload, get_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token, get_secret(), algorithms=[ALGORITHM], audience=AUDIENCE,
        issuer=ISSUER, options={'require': ['sub', 'iat', 'nbf', 'exp', 'pv']},
        leeway=15,
    )


def token_matches_user(claims: dict, user) -> bool:
    return hmac.compare_digest(str(claims.get('pv', '')), _credential_version(user.senha))
