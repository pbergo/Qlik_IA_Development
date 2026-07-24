-- ============================================================================
-- VendasODS — Oracle: pre-requisitos de INSTANCIA para o CDC (LogMiner) do
-- Qlik Data Movement Gateway. Roda ANTES de cdc_config_vendasods.sql.
--
-- Diferente dos outros scripts deste diretorio (usuario/grants/tabelas/dados,
-- que rodam como 'system' ou 'vendasods'), este aqui mexe em configuracao de
-- BANCO/INSTANCIA e precisa ser executado como SYSDBA:
--   sqlplus sys/<senha>@//<host>:<porta>/<service> as sysdba
--
-- Sem isso, a tarefa CDC falha ao iniciar com o erro observado em deploy real:
--   [SOURCE_UNLOAD]E: Minimal database supplemental logging level is not
--   enabled [1020418]
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) Supplemental logging minimo (nivel banco/geral) — operacao ONLINE, nao
--    exige reiniciar a instancia. Necessario para o LogMiner identificar as
--    linhas alteradas nos redo logs.
-- ----------------------------------------------------------------------------

-- Checar o estado atual (esperado: YES depois do ALTER abaixo)
SELECT supplemental_log_data_min FROM v$database;

ALTER DATABASE ADD SUPPLEMENTAL LOG DATA;

-- Confirmar
SELECT supplemental_log_data_min FROM v$database;

-- ----------------------------------------------------------------------------
-- 2) Modo ARCHIVELOG — tambem costuma ser exigido pelo conector Oracle do
--    Data Movement Gateway. ATENCAO: o bloco SHUTDOWN/STARTUP abaixo derruba
--    TODAS as conexoes da instancia (inclusive esta sessao) e precisa ser
--    executado interativamente, em uma sessao sqlplus local/direta como
--    SYSDBA no host do banco (nao via uma ferramenta remota automatizada).
--    Rodar apenas se o SELECT abaixo NAO retornar 'ARCHIVELOG'.
-- ----------------------------------------------------------------------------

-- Checar o modo atual
SELECT log_mode FROM v$database;
-- equivalente: ARCHIVE LOG LIST;

-- Se log_mode = 'NOARCHIVELOG', habilitar (executar linha a linha, interativo):
-- SHUTDOWN IMMEDIATE;
-- STARTUP MOUNT;
-- ALTER DATABASE ARCHIVELOG;
-- ALTER DATABASE OPEN;

-- Confirmar depois do ALTER acima
-- SELECT log_mode FROM v$database;

-- Nota: em instancias de dev/teste (ex. container oracle-xe), validar espaco
-- disponivel na Fast Recovery Area (DB_RECOVERY_FILE_DEST_SIZE) — se encher,
-- a instancia trava aguardando archive. Ajustar com:
-- ALTER SYSTEM SET db_recovery_file_dest_size = 10G SCOPE=BOTH;
