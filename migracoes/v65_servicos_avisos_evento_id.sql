-- V6.5: Rastreabilidade dos avisos internos. NAO executar automaticamente.
-- Compatibilidade: os avisos historicos mantem evento_id NULL.
-- Aplicar SOMENTE no ambiente explicitamente autorizado, apos backup.
BEGIN;
ALTER TABLE public.servicos_avisos
    ADD COLUMN IF NOT EXISTS evento_id INTEGER
    REFERENCES public.servicos_eventos(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_servicos_avisos_evento_id
    ON public.servicos_avisos(evento_id);
COMMIT;
