-- ============================================================================
-- VendasODS — Oracle: criacao do usuario e grants para o Qlik Data
-- Analytics Direct Access Gateway (conexao 'da-oracle', extracao via SQL
-- direto pelos scripts ext001/ext002/ext003) + grants de DDL usados pelo
-- script create_database_vendasods.sql deste mesmo diretorio.
--
-- Este projeto NAO usa Change Data Capture (Data Movement Gateway/
-- LogMiner) - a extracao e feita por SQL direto (SELECT/full ou por janela
-- de dias), entao os grants de leitura de redo log/LogMiner que um setup
-- de CDC exigiria (DBMS_LOGMNR, V$LOGMNR_*, V$ARCHIVED_LOG, V$LOG, etc.)
-- nao sao necessarios aqui e foram omitidos.
-- ============================================================================

create user vendasods identified by Qlik1234;
grant create session to vendasods;
grant connect to vendasods;
grant unlimited tablespace TO vendasods;
grant create any table TO vendasods;
grant create any index TO vendasods;
grant alter any table TO vendasods;
grant drop any table TO vendasods;
grant insert any table TO vendasods;
grant update any table TO vendasods;
grant delete any table TO vendasods;
grant select any table TO vendasods;

grant select on all_indexes TO vendasods;
grant select on all_ind_columns TO vendasods;
grant select on all_constraints TO vendasods;
grant select on all_cons_columns TO vendasods;

GRANT CREATE TRIGGER TO vendasods;

-- Necessario para create_database_vendasods.sql (secao 3: SEQUENCE + TRIGGER
-- usadas para emular o AUTO_INCREMENT do MySQL nas colunas Devolucao_ID e
-- Devolucao_Item_ID). Sem este grant, os CREATE SEQUENCE falham com ORA-01031.
GRANT CREATE SEQUENCE TO vendasods;
