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
END
$haize$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_preferencias_telefone
  ON whatsapp_preferencias(telefone)
  WHERE telefone IS NOT NULL;
COMMIT;
