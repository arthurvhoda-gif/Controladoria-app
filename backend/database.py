"""Conexão do PostgreSQL da Controladoria Haize.

Configure DATABASE_URL somente no Render (produção) ou no ambiente local.
Nunca salve senhas, tokens ou URLs com credenciais no repositório.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurada. "
        "Defina a URL do PostgreSQL no Environment do Render antes de publicar esta versão."
    )

# Compatibilidade com URIs fornecidas por plataformas antigas.
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = (
        "postgresql://" + SQLALCHEMY_DATABASE_URL[len("postgres://"):]
    )

# Verifica conexões reaproveitadas antes de utilizá-las; importante para o Neon.
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
