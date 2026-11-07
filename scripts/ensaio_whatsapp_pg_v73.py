# -*- coding: utf-8 -*-
"""Ensaio REAL de concorrencia PostgreSQL isolado na CI.

NUNCA executa contra Neon ou producao; o banco permitido possui nome fixo
e hostname loopback. Testa uma corrida entre consentimento e troca de telefone.
Nenhuma mensagem e enviada.
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from urllib.parse import urlsplit

from fastapi import HTTPException

url = urlsplit(os.environ.get('DATABASE_URL', ''))
if (url.scheme not in ('postgresql', 'postgresql+psycopg2')
        or url.hostname not in ('127.0.0.1', 'localhost')
        or url.path != '/haize_v73_notificacoes'):
    raise SystemExit('BLOQUEADO: só aceita PostgreSQL descartável local haize_v73_notificacoes.')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from database import engine, SessionLocal
import models
import whatsapp_alertas as wa

models.Base.metadata.create_all(engine)


def req(uid):
    return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid))


with SessionLocal() as db:
    db.add_all([
        models.Condominio(id=1, nome='Condominio de teste'),
        models.Usuario(id=1, nome='Controladoria Teste', email='gestora@local.test',
                       senha='hash-ficticio', perfil='Controladoria'),
        models.Usuario(id=2, nome='Zelador Teste', email='zelador@local.test',
                       senha='hash-ficticio', perfil='Checklist', condominio_id=1),
    ])
    db.commit()
    wa.salvar_numero_admin(2, wa.NumeroAdministrado(numero='43999991111'),
                           req(1), db)

iniciado = Event()
telefone_visto = '+5543999991111'


def tentar_autorizar():
    with SessionLocal() as db:
        iniciado.set()
        try:
            wa.salvar_preferencias(
                wa.PreferenciaEntrada(receber_alertas=True,
                                     numero_confirmado=telefone_visto),
                req(2), db)
        except HTTPException as erro:
            return erro.status_code
        return 200


with SessionLocal() as admin_db:
    # Transacao A: manter linha do titular bloqueada ate troca oficial do numero.
    pessoa, prefs = wa.contato_bloqueado_para_edicao(admin_db, 2)
    assert pessoa.id == 2 and prefs.telefone == telefone_visto
    with ThreadPoolExecutor(max_workers=1) as executor:
        tentativa = executor.submit(tentar_autorizar)
        assert iniciado.wait(timeout=5), 'A segunda requisicao nao iniciou.'
        time.sleep(0.25)
        bloqueado_durante_troca = not tentativa.done()
        # Esta operacao atualiza contato, revoga consentimento e comita, liberando
        # o lock. O usuario concorrente DEVE reler o telefone atualizado.
        troca = wa.salvar_numero_admin(
            2, wa.NumeroAdministrado(numero='43988882222'), req(1), admin_db)
        resultado = tentativa.result(timeout=8)

assert bloqueado_durante_troca, 'O consentimento nao esperou o bloqueio da conta.'
assert troca['numero'] == '+5543988882222'
assert resultado == 409, 'Consentimento antigo passou para novo numero.'
with SessionLocal() as db:
    pref = db.get(models.PreferenciaWhatsApp, 2)
    assert pref.telefone == '+5543988882222' and not pref.consentimento
    assert db.query(models.WhatsAppAuditoriaConsentimento).count() == 0
    assert db.query(models.WhatsAppAuditoriaContato).count() == 2

print('V7.3: PostgreSQL real confirma bloqueio concorrente, troca segura e opt-in 409. OK.')
