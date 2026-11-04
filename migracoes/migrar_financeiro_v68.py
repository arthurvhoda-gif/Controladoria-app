# -*- coding: utf-8 -*-
"""Migração EXCLUSIVAMENTE local da Central Financeira V6.8.

Faz backup completo com pg_dump antes de qualquer ALTER/CREATE.
Não recebe URLs arbitrárias; sempre 127.0.0.1:5432/haize_v61_teste.
Não deve ser usado para produção. Promoveções exigem plano à parte.
"""
from datetime import datetime
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


ROOT = Path(__file__).resolve().parents[1]
USUARIO = 'haize_v61_app'
DATABASE = 'haize_v61_teste'
HOST = '127.0.0.1'
PORT = 5432


def localizar_pg_dump():
    encontrado = shutil.which('pg_dump')
    if encontrado:
        return encontrado
    # Caminho padrão do PostgreSQL instalado no Windows.
    for v in ('18', '17', '16', '15'):
        caminho = Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'PostgreSQL' / v / 'bin' / 'pg_dump.exe'
        if caminho.is_file():
            return str(caminho)
    raise RuntimeError('pg_dump não encontrado. Instale as ferramentas cliente PostgreSQL antes de migrar.')


def migrar():
    if os.name != 'nt':
        raise SystemExit('Segurança: esta migração de testes foi preparada apenas para Windows local.')
    print('DESTINO EXCLUSIVO: PostgreSQL 127.0.0.1:5432 / haize_v61_teste')
    print('Nunca informe senha do Neon/Render. Use somente a senha LOCAL de testes.')
    conf = input('Digite MIGRAR-LOCAL para confirmar: ').strip()
    if conf != 'MIGRAR-LOCAL':
        raise SystemExit('Cancelado sem alterações.')
    pg_dump = localizar_pg_dump()
    senha = getpass.getpass('Senha do PostgreSQL LOCAL de testes: ')
    url = URL.create('postgresql+psycopg', username=USUARIO, password=senha,
                     host=HOST, port=PORT, database=DATABASE)
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        base = conn.execute(text('SELECT current_database()')).scalar_one()
        addr = conn.execute(text('SELECT host(inet_server_addr())')).scalar_one_or_none()
        if base != DATABASE or addr not in ('127.0.0.1', '::1'):
            raise RuntimeError('Destino de banco inesperado; migração cancelada.')
        quantidade = conn.execute(text('SELECT COUNT(*) FROM solicitacoes')).scalar_one()
        print('Solicitações existentes:', quantidade)
    destino = Path(os.environ['LOCALAPPDATA']) / 'HaizeControladoriaTestes' / 'backups'
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f'haize_v68_antes_{datetime.now():%Y%m%d_%H%M%S}.backup'
    env = dict(os.environ, PGPASSWORD=senha)
    print('Criando backup local, antes de qualquer alteração...')
    res = subprocess.run([pg_dump, '-h', HOST, '-p', str(PORT), '-U', USUARIO,
                          '-d', DATABASE, '--format=custom', '--no-owner',
                          '--file', str(arquivo)], env=env, capture_output=True, text=True)
    if res.returncode or not arquivo.is_file() or arquivo.stat().st_size < 100:
        if arquivo.exists():
            arquivo.unlink()
        raise RuntimeError('Backup falhou; nenhuma migração executada. ' + res.stderr[:800])
    print('Backup salvo em:', arquivo)
    # Importe modelos somente depois de confirmar o destino; aqui não importamos main.
    os.environ['DATABASE_URL'] = url.render_as_string(hide_password=False)
    sys.path.insert(0, str(ROOT / 'backend'))
    import models
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE solicitacoes ADD COLUMN IF NOT EXISTS solicitante_id INTEGER'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_solicitacoes_solicitante_id ON solicitacoes(solicitante_id)'))
        conn.execute(text('''DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_solicitacoes_solicitante_id') THEN
                ALTER TABLE solicitacoes ADD CONSTRAINT fk_solicitacoes_solicitante_id
                FOREIGN KEY (solicitante_id) REFERENCES usuarios(id) ON DELETE SET NULL;
            END IF;
        END $$'''))
        # Nomes repetidos não produzem atribuição; somente caso UNÍVOCO.
        conn.execute(text('''WITH candidatos AS (
            SELECT s.id AS sid, MIN(u.id) AS uid
            FROM solicitacoes s JOIN usuarios u
              ON LOWER(TRIM(s.solicitante)) = LOWER(TRIM(u.nome))
            WHERE s.solicitante_id IS NULL
            GROUP BY s.id HAVING COUNT(*) = 1
        )
        UPDATE solicitacoes s SET solicitante_id = c.uid
        FROM candidatos c WHERE s.id = c.sid'''))
        modelos = [models.FinanceiroLancamento.__table__, models.FinanceiroComprovante.__table__]
        models.Base.metadata.create_all(bind=conn, tables=modelos, checkfirst=True)
        n_amb = conn.execute(text('SELECT COUNT(*) FROM solicitacoes WHERE solicitante_id IS NULL')).scalar_one()
        n_ok = conn.execute(text('SELECT COUNT(*) FROM solicitacoes WHERE solicitante_id IS NOT NULL')).scalar_one()
    print('MIGRAÇÃO LOCAL CONCLUÍDA. Vínculos identificados:', n_ok, '| Legados pendentes de revisão:', n_amb)
    print('Não alterou nenhuma conta de produção. Guarde o backup local com segurança.')


if __name__ == '__main__':
    migrar()
