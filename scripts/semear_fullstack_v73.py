# -*- coding: utf-8 -*-
"""Cria SOMENTE dados ficticios de homologacao integrada local da CI.

Bloqueia destinos externos; banco descartavel, sem Neon, sem contatos reais.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

url = urlsplit(os.environ.get('DATABASE_URL', ''))
if (url.scheme not in ('postgresql', 'postgresql+psycopg2')
        or url.hostname not in ('127.0.0.1', 'localhost')
        or url.path != '/haize_v73_integracao'):
    raise SystemExit('BLOQUEADO: somente PostgreSQL local haize_v73_integracao.')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from database import engine, SessionLocal
import auth_utils
import models

models.Base.metadata.create_all(engine)

senha = 'SenhaFicticiaDeTeste123'
with SessionLocal() as db:
    if db.query(models.Usuario).count():
        raise SystemExit('BLOQUEADO: o banco de homologacao nao esta vazio.')
    db.add_all([
        models.Condominio(id=1, nome='Condominio Ficticio Alfa'),
        models.Condominio(id=2, nome='Condominio Ficticio Beta'),
    ])
    db.flush()
    db.add_all([
        models.Usuario(
            id=1, nome='Gestora Ficticia', email='gestora@teste.local',
            senha=auth_utils.hash_password(senha), perfil='Controladoria',
        ),
        models.Usuario(
            id=2, nome='Zelador Alfa', email='zelador.alfa@teste.local',
            senha=auth_utils.hash_password(senha), perfil='Checklist', condominio_id=1,
        ),
        models.Usuario(
            id=3, nome='Zelador Beta', email='zelador.beta@teste.local',
            senha=auth_utils.hash_password(senha), perfil='Checklist', condominio_id=2,
        ),
    ])
    db.commit()

print('V7.3: dados ficticios criados em PostgreSQL local de integracao. OK.')
