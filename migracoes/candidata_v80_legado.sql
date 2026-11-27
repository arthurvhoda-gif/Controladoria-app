-- CANDIDATO V8.0: somente ensaio isolado; não aplicar em produção.
-- Executar em uma transação única, antes de importar main.
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.solicitacoes, public.anexos, public.historico_solicitacoes,
 public.checklist_execucoes, public.checklist_envios_relatorios IN ACCESS EXCLUSIVE MODE;
ALTER TABLE public.solicitacoes ADD COLUMN IF NOT EXISTS solicitante_id integer;
CREATE INDEX IF NOT EXISTS ix_solicitacoes_solicitante_id ON public.solicitacoes(solicitante_id);
DO $m$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid='public.solicitacoes'::regclass
      AND contype='f' AND confrelid='public.usuarios'::regclass
      AND conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid='public.solicitacoes'::regclass AND attname='solicitante_id')]::smallint[]
      AND confkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid='public.usuarios'::regclass AND attname='id')]::smallint[]
      AND confdeltype='n'
  ) THEN
    ALTER TABLE public.solicitacoes ADD CONSTRAINT fk_solicitacoes_solicitante_id
      FOREIGN KEY(solicitante_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;
  END IF;
END $m$;
-- Vínculos históricos ficam nulos até confirmação pela Controladoria.
DO $m$
DECLARE t text; fk record; tem_registros boolean;
BEGIN
  FOREACH t IN ARRAY ARRAY['anexos','historico_solicitacoes'] LOOP
    FOR fk IN SELECT conname FROM pg_constraint
      WHERE conrelid=to_regclass('public.'||t) AND contype='f'
        AND confrelid='public.solicitacoes_compra'::regclass
        AND conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid=to_regclass('public.'||t) AND attname='solicitacao_id')]::smallint[]
    LOOP
      EXECUTE format('SELECT EXISTS (SELECT 1 FROM public.%I)',t) INTO tem_registros;
      IF tem_registros THEN RAISE EXCEPTION 'V8.0 BLOQUEADA: referencias legadas exigem conciliacao: %',t; END IF;
      EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I',t,fk.conname);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.'||t)
        AND contype='f' AND confrelid='public.solicitacoes'::regclass
        AND conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid=to_regclass('public.'||t) AND attname='solicitacao_id')]::smallint[]
        AND confkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid='public.solicitacoes'::regclass AND attname='id')]::smallint[]) THEN
      EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY(solicitacao_id) REFERENCES public.solicitacoes(id)',t,'fk_v80_'||t||'_solicitacao');
    END IF;
  END LOOP;
END $m$;
-- O ORM da versão antiga e da V8 usa strings nestes campos.
ALTER TABLE public.anexos ALTER COLUMN data_upload TYPE varchar USING data_upload::text;
ALTER TABLE public.historico_solicitacoes ALTER COLUMN data TYPE varchar USING data::text;
-- Preservar relatórios órfãos, sem reutilizar seus identificadores de execução.
DO $m$
DECLARE proximo bigint; reservado bigint; ultimo bigint; chamado boolean;
BEGIN
  IF pg_get_serial_sequence('public.checklist_execucoes','id') <> 'public.checklist_execucoes_id_seq'
  THEN RAISE EXCEPTION 'Sequencia de checklist inesperada'; END IF;
  SELECT last_value,is_called INTO ultimo,chamado FROM public.checklist_execucoes_id_seq;
  SELECT GREATEST(COALESCE((SELECT max(id) FROM public.checklist_execucoes),0),
                  COALESCE((SELECT max(execucao_id) FROM public.checklist_envios_relatorios),0)) INTO reservado;
  proximo := GREATEST(ultimo + CASE WHEN chamado THEN 1 ELSE 0 END,reservado+1);
  IF proximo>ultimo+CASE WHEN chamado THEN 1 ELSE 0 END THEN
    EXECUTE format('ALTER SEQUENCE public.checklist_execucoes_id_seq RESTART WITH %s',proximo);
  END IF;
END $m$;
