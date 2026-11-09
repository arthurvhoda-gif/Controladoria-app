-- Controladoria Haize V7.3 - aplicacao SOMENTE mediante homologacao e backup.
-- NAO executar automaticamente no Render/Neon/CI. Nao altera consentimentos
-- nem apaga cadastros. Impede o mesmo numero em duas contas.
--
-- Preflight (apenas consulta, seguro):
-- SELECT telefone, COUNT(*) AS total
-- FROM whatsapp_preferencias
-- WHERE telefone IS NOT NULL
-- GROUP BY telefone HAVING COUNT(*) > 1;
--
-- Se houver linhas, investigar as contas e autorizações com a Controladoria
-- ANTES de aplicar. Jamais escolher destinatario automaticamente.
BEGIN;
DO $haize$
BEGIN
  IF EXISTS (
    SELECT 1 FROM whatsapp_preferencias
    WHERE telefone IS NOT NULL
    GROUP BY telefone HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION 'V7.3 BLOQUEADA: telefones duplicados. Corrija os cadastros antes de criar a restricao.';
  END IF;

  -- IF NOT EXISTS, sozinho, aceita um indice de mesmo nome NAO unico ou
  -- apontando para outra tabela. Esse estado seria falha silenciosa grave.
  -- Aceita o UNIQUE completo criado pelo SQLAlchemy ou o parcial da V7.3.
  IF to_regclass('public.uq_whatsapp_preferencias_telefone') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1
         FROM pg_class idx
         JOIN pg_index i ON i.indexrelid = idx.oid
         JOIN pg_attribute a ON a.attrelid = i.indrelid
           AND a.attnum = i.indkey[0]
        WHERE idx.oid = to_regclass('public.uq_whatsapp_preferencias_telefone')
          AND i.indrelid = to_regclass('public.whatsapp_preferencias')
          AND i.indisunique AND i.indisvalid AND i.indisready
          AND i.indnkeyatts = 1 AND i.indnatts = 1
          AND a.attname = 'telefone'
          AND (
            i.indpred IS NULL
            OR pg_get_expr(i.indpred, i.indrelid)
               IN ('(telefone IS NOT NULL)', 'telefone IS NOT NULL')
          )
     ) THEN
    RAISE EXCEPTION 'V7.3 BLOQUEADA: nome do indice existente nao garante unicidade do telefone.';
  END IF;
END
$haize$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_preferencias_telefone
  ON whatsapp_preferencias(telefone)
  WHERE telefone IS NOT NULL;
COMMIT;
