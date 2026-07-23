-- ============================================================================
-- VendasODS — Oracle: criacao do usuario e grants para Qlik Data Integration
-- (Data Movement Gateway / CDC log-based) + grants de DDL usados pelo
-- script create_database_vendasods.sql deste mesmo diretorio.
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

grant  select any table                 to vendasods;
grant  select any transaction           to vendasods;
grant  select on V$ARCHIVED_LOG        to vendasods;
grant  select on V$LOG                 to vendasods;
grant  select on V$LOGFILE             to vendasods;
grant  select on V$DATABASE            to vendasods;
grant  select on V$THREAD              to vendasods;
grant  select on V$PARAMETER           to vendasods;
grant  select on V$NLS_PARAMETERS      to vendasods;
grant  select on V$TIMEZONE_NAMES      to vendasods;
grant  select on V$TRANSACTION         to vendasods;
grant  select on ALL_INDEXES            to vendasods;
grant  select on ALL_OBJECTS            to vendasods;
grant  select on DBA_OBJECTS            to vendasods;
grant  select on ALL_TABLES             to vendasods;
grant  select on ALL_USERS              to vendasods;
grant  select on ALL_CATALOG            to vendasods;
grant  select on ALL_CONSTRAINTS        to vendasods;
grant  select on ALL_CONS_COLUMNS       to vendasods;
grant  select on ALL_TAB_COLS           to vendasods;
grant  select on ALL_IND_COLUMNS        to vendasods;
grant  select on ALL_LOG_GROUPS         to vendasods;
grant  select on SYS.DBA_REGISTRY       to vendasods;
grant  select on SYS.OBJ$               to vendasods;
grant  select on SYS.ENC$               to vendasods;
#grant  select, create, update, delete on DBA_TABLESPACES        to vendasods;
grant  select on ALL_TAB_PARTITIONS     to vendasods;
grant  select on ALL_ENCRYPTED_COLUMNS  to vendasods;
grant select on V$DATABASE_INCARNATION to vendasods;
grant select on V$CONTAINERS to vendasods;

grant  select on ALL_VIEWS              to vendasods;
grant alter any table to vendasods;
grant create any directory to vendasods;
grant select on all_directories to vendasods;

grant execute on DBMS_LOGMNR          to vendasods;
grant select on V$LOGMNR_LOGS        to vendasods;
grant select on V$LOGMNR_CONTENTS    to vendasods;

grant select on v$transportable_platform  to vendasods;

grant execute on DBMS_FILE_TRANSFER TO  vendasods;
grant execute on DBMS_FILE_GROUP to vendasods;


GRANT CREATE TRIGGER TO vendasods;

-- Necessario para create_database_vendasods.sql (secao 3: SEQUENCE + TRIGGER
-- usadas para emular o AUTO_INCREMENT do MySQL nas colunas Devolucao_ID e
-- Devolucao_Item_ID). Sem este grant, os CREATE SEQUENCE falham com ORA-01031.
GRANT CREATE SEQUENCE TO vendasods;
