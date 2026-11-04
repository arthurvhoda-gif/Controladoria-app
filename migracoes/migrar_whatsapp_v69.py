"""Adiciona tipo_evento somente no banco LOCAL, com backup previo."""
import getpass
import os
from datetime import datetime
from pathlib import Path
import subprocess
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from migrar_financeiro_v68 import localizar_pg_dump

def migrar():
    if os.name != 'nt':
        raise SystemExit('Somente Windows local.')
    print('Destino: 127.0.0.1:5432/haize_v61_teste. Nao usa DATABASE_URL.')
    if input('Digite MIGRAR-LOCAL: ').strip() != 'MIGRAR-LOCAL':
        raise SystemExit('Cancelado.')
    dump = localizar_pg_dump()
    senha = getpass.getpass('Senha LOCAL de haize_v61_app: ')
    url = URL.create('postgresql+psycopg', username='haize_v61_app', password=senha,
                     host='127.0.0.1', port=5432, database='haize_v61_teste')
    engine = create_engine(url)
    with engine.connect() as conn:
        base, addr = conn.execute(text('SELECT current_database(), host(inet_server_addr())')).one()
        if base != 'haize_v61_teste' or addr not in ('127.0.0.1', '::1'):
            raise RuntimeError('Destino inesperado.')
    pasta = Path(os.environ['LOCALAPPDATA']) / 'HaizeControladoriaTestes' / 'backups'
    pasta.mkdir(parents=True, exist_ok=True)
    backup = pasta / ('haize_v69_antes_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.backup')
    res = subprocess.run([dump, '-h', '127.0.0.1', '-p', '5432', '-U', 'haize_v61_app',
        '-d', 'haize_v61_teste', '--format=custom', '--no-owner', '--file', str(backup)],
        env=dict(os.environ, PGPASSWORD=senha), capture_output=True, text=True)
    if res.returncode or not backup.exists() or backup.stat().st_size < 100:
        raise RuntimeError('Backup falhou. Nenhuma alteracao no banco. Arquivo parcial preservado.')
    print('Backup:', backup)
    with engine.begin() as conn:
        conn.execute(text('SET LOCAL lock_timeout = \'5s\''))
        conn.execute(text('ALTER TABLE servicos_avisos ADD COLUMN IF NOT EXISTS tipo_evento VARCHAR(32)'))
        formato = conn.execute(text("SELECT data_type, character_maximum_length, is_nullable FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='servicos_avisos' AND column_name='tipo_evento'")).one()
        if tuple(formato) != ('character varying', 32, 'YES'):
            raise RuntimeError('Coluna preexistente incompativel; transacao revertida.')
    engine.dispose()
    print('Migracao local concluida. Avisos antigos preservados; nenhum envio.')

if __name__ == '__main__':
    migrar()
