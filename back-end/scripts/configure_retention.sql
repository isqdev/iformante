-- Neon: configure cron.database_name no provedor para este banco e reinicie o compute.
-- Mantenha o compute ativo para executar diariamente.
CREATE EXTENSION IF NOT EXISTS pg_cron;
-- 03:00 UTC = 00:00 America/Sao_Paulo.
SELECT cron.schedule('iformante-daily-retention', '0 3 * * *', 'SELECT public.cleanup_iformante_expired()');
