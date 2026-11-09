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

# Migração V7.3: em bases legadas um mesmo telefone pode ter dois titulares.
# Validar que o script falha sem apagar cadastros; depois valida que cria
# restrição quando a Controladoria já desfez a duplicidade.
import psycopg2

with SessionLocal() as db:
    db.add(models.Usuario(id=3, nome='Colaborador de teste',
                          email='interno@local.test', senha='hash-ficticio',
                          perfil='Solicitante'))
    db.commit()

with engine.begin() as conn:
    conn.exec_driver_sql(
        'ALTER TABLE whatsapp_preferencias '
        'DROP CONSTRAINT uq_whatsapp_preferencias_telefone'
    )
    conn.exec_driver_sql(
        "INSERT INTO whatsapp_preferencias "
        "(usuario_id, telefone, consentimento, atualizado_em) "
        "VALUES (3, '+5543988882222', 0, CURRENT_TIMESTAMP)"
    )

script_migracao = (
    Path(__file__).resolve().parents[1]
    / 'migracoes' / 'v73_whatsapp_telefone_unico.sql'
).read_text(encoding='utf-8')

import preflight_migracao_whatsapp_v73 as preflight


def conferir_preflight():
    # Só conexão CI local permitida. Transação READ ONLY, sem exibir telefones.
    destino = preflight.validar_destino()
    conn = psycopg2.connect(destino)
    try:
        resposta = preflight.avaliar_readonly(conn)
        assert '+55' not in str(resposta), 'Pré-verificação expôs um telefone.'
        return resposta
    finally:
        conn.close()


def aplicar_migracao():
    # O script contem BEGIN/COMMIT e deve ser executado inteiro.
    conexao = psycopg2.connect(os.environ['DATABASE_URL'])
    conexao.autocommit = True
    try:
        with conexao.cursor() as cursor:
            cursor.execute(script_migracao)
    finally:
        conexao.close()


pre_duplicado = conferir_preflight()
assert pre_duplicado['situacao'] == 'bloqueado'
assert pre_duplicado['grupos_duplicados'] == 1
assert pre_duplicado['contas_afetadas'] == 2
assert pre_duplicado['indice_unico_valido'] is False

try:
    aplicar_migracao()
except psycopg2.Error as erro:
    assert 'V7.3 BLOQUEADA' in str(erro), (
        'A migração falhou por motivo diferente de telefone duplicado.'
    )
else:
    raise AssertionError('Migração aceitou números duplicados indevidamente.')

with engine.begin() as conn:
    quantidade = conn.exec_driver_sql(
        "SELECT count(*) FROM whatsapp_preferencias "
        "WHERE telefone = '+5543988882222'"
    ).scalar_one()
    assert quantidade == 2, 'Pré-validação alterou dados legados indevidamente.'
    conn.exec_driver_sql(
        'DELETE FROM whatsapp_preferencias WHERE usuario_id = 3'
    )

pre_limpo = conferir_preflight()
assert pre_limpo['situacao'] == 'pronto_para_migracao_na_copia'
assert pre_limpo['grupos_duplicados'] == 0
assert pre_limpo['indice_unico_valido'] is False

aplicar_migracao()
aplicar_migracao()  # idempotente, sem alterar cadastros ou consentimentos
pos_migracao = conferir_preflight()
assert pos_migracao['situacao'] == 'migracao_ja_aplicada_na_copia'
assert pos_migracao['indice_unico_valido'] is True

# Regressão: um índice NÃO UNIQUE com o mesmo nome jamais pode ser confundido
# com a restrição pretendida por CREATE INDEX IF NOT EXISTS.
with engine.begin() as conn:
    conn.exec_driver_sql('DROP INDEX uq_whatsapp_preferencias_telefone')
    conn.exec_driver_sql(
        'CREATE INDEX uq_whatsapp_preferencias_telefone '
        'ON whatsapp_preferencias (telefone)'
    )
pre_indice_invalido = conferir_preflight()
assert pre_indice_invalido['situacao'] == 'bloqueado'
assert pre_indice_invalido['indice_unico_valido'] is False
try:
    aplicar_migracao()
except psycopg2.Error as erro:
    assert 'V7.3 BLOQUEADA' in str(erro)
    assert 'indice' in str(erro).lower()
else:
    raise AssertionError('Migração aceitou índice existente NÃO UNIQUE.')

with engine.begin() as conn:
    conn.exec_driver_sql('DROP INDEX uq_whatsapp_preferencias_telefone')
aplicar_migracao()
assert conferir_preflight()['situacao'] == 'migracao_ja_aplicada_na_copia'
with engine.connect() as conn:
    indices = conn.exec_driver_sql(
        "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' "
        "AND tablename = 'whatsapp_preferencias' "
        "AND indexname = 'uq_whatsapp_preferencias_telefone'"
    ).all()
    assert len(indices) == 1 and 'UNIQUE INDEX' in indices[0][0], (
        'Índice UNIQUE não criado após limpeza dos duplicados.'
    )
# Comprovar a saída do CLI: apenas agregados, sem telefone e sem escrita.
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

saida_cli = io.StringIO()
with redirect_stdout(saida_cli):
    assert preflight.main() == 0
relatorio_cli = json.loads(saida_cli.getvalue())
assert relatorio_cli['situacao'] == 'migracao_ja_aplicada_na_copia'
assert '+55' not in saida_cli.getvalue()
assert 'haize_ci' not in saida_cli.getvalue()

# Guardas devem impedir hosts externos e redirecionamento por query string.
for url_fora in (
    'postgresql://haize_ci:ficticio@neon.exemplo:5432/haize_v73_notificacoes',
    'postgresql://haize_ci:ficticio@127.0.0.1:5432/haize_v73_notificacoes?host=neon.exemplo',
):
    with patch.dict(os.environ, {'DATABASE_URL': url_fora}):
        try:
            preflight.validar_destino()
        except SystemExit as erro:
            assert 'BLOQUEADO' in str(erro)
        else:
            raise AssertionError('Preflight aceitou banco remoto ou URL adulterada.')

print('V7.3: preflight somente leitura, índice válido e recusas anti-produção. OK.')
print('V7.3: migração bloqueia legado duplicado e aplica UNIQUE após saneamento. OK.')


# Pré-conferência transacional: garantir ordem de locks sem deadlock.
# Uma alteração administrativa do telefone deve vencer e fazer a conferência
# observar a fila CANCELADA. Nenhum serviço externo é acionado.
from datetime import date, timedelta
import servicos_api as servicos

with SessionLocal() as db:
    wa.salvar_preferencias(
        wa.PreferenciaEntrada(receber_alertas=True,
                             numero_confirmado='+5543988882222'),
        req(2), db,
    )
    novo_servico = servicos.criar(servicos.ServicoNovo(
        condominio_id=1, executores_ids=[2],
        titulo='Conferir casa de máquinas',
        descricao='Tarefa de concorrência inteiramente fictícia',
        prazo=date.today() + timedelta(days=2),
    ), req(1), db)
    fila_id = db.query(models.FilaWhatsApp).filter(
        models.FilaWhatsApp.servico_id == novo_servico['id'],
        models.FilaWhatsApp.usuario_id == 2,
    ).one().id

verificacao_iniciada = Event()


def verificar_com_lock():
    with SessionLocal() as db:
        verificacao_iniciada.set()
        return wa.verificar_aviso_preparado(fila_id, req(1), db)


with SessionLocal() as admin_db:
    usuario_bloqueado, _ = wa.contato_bloqueado_para_edicao(admin_db, 2)
    assert usuario_bloqueado.id == 2
    with ThreadPoolExecutor(max_workers=1) as executor:
        conferencia = executor.submit(verificar_com_lock)
        assert verificacao_iniciada.wait(timeout=5), 'Conferência não iniciou.'
        time.sleep(0.25)
        assert not conferencia.done(), 'Conferência ignorou lock administrativo.'
        troca_final = wa.salvar_numero_admin(
            2, wa.NumeroAdministrado(numero='43999993333'),
            req(1), admin_db)
        resultado_verificacao = conferencia.result(timeout=8)

assert troca_final['alterado'] is True
assert resultado_verificacao['situacao'] == 'impedido'
assert resultado_verificacao['envio_autorizado'] is False
assert resultado_verificacao['status_fila'] == 'cancelada'
with SessionLocal() as db:
    assert db.get(models.FilaWhatsApp, fila_id).status == 'cancelada'
    assert not db.get(models.PreferenciaWhatsApp, 2).consentimento
print('V7.3: pré-conferência observa revogação concorrente SEM deadlock. OK.')
