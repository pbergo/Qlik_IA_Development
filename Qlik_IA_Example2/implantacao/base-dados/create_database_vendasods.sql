-- ============================================================================
-- VendasODS — Oracle: criacao do banco/schema e das tabelas
-- Alvo: Oracle Database 21c XE (schema VENDASODS)
-- Estrutura convertida a partir da origem MySQL (192.168.1.27:3306,
-- database vendasods) e validada ao vivo em 192.168.1.27:1521/XEPDB1.
--
-- Pre-requisito: o usuario/schema "vendasods" e os grants de sessao/DDL
-- (CREATE SESSION, CREATE ANY TABLE, ALTER ANY TABLE, etc. + os grants de
-- CDC do Data Movement Gateway) sao criados por um script separado
-- (config de CDC). Este script assume que o usuario "vendasods" ja existe
-- e esta conectado (rodar como vendasods).
--
-- IMPORTANTE: alem do "GRANT CREATE TRIGGER TO vendasods" ja previsto no
-- script de CDC, este script tambem precisa de:
--   GRANT CREATE SEQUENCE TO vendasods;
-- (usado nas sequences de auto increment da secao 3 abaixo). Sem esse
-- grant, os CREATE SEQUENCE desta secao falham com ORA-01031.
--
-- Ordem de execucao deste arquivo:
--   1. CREATE TABLE (13 tabelas, sem FK inline)
--   2. FOREIGN KEYS
--   3. AUTO INCREMENT (SEQUENCE + TRIGGER — equivalente ao AUTO_INCREMENT
--      do MySQL; IDENTITY nativo do Oracle nao se aplica aqui pois so
--      pode ser definido na criacao da coluna, e aqui a coluna ja nasce
--      junto com a tabela, entao usamos o mesmo padrao consolidado no
--      ambiente ja validado, por consistencia com scripts incrementais)
--   4. UNIQUE / CHECK constraints
--   5. Coluna calculada (trigger) e defaults equivalentes ao MySQL
-- ============================================================================


-- ============================================================================
-- 1. CREATE TABLE
-- ============================================================================

CREATE TABLE "Departamento" (
  "Departamento"    NVARCHAR2(255),
  "Departamento_ID" NUMBER(10) NOT NULL,
  CONSTRAINT "Departamento_PRIMARY" PRIMARY KEY ("Departamento_ID")
);

CREATE TABLE "Categoria" (
  "Categoria"       NVARCHAR2(255),
  "Categoria_ID"    NUMBER(10) NOT NULL,
  "Departamento_ID" NUMBER(10) NOT NULL,
  CONSTRAINT "Categoria_PRIMARY" PRIMARY KEY ("Categoria_ID")
);

CREATE TABLE "Cidades" (
  "Cliente_Cidade" NVARCHAR2(255),
  "Cliente_Pais"   NVARCHAR2(255),
  "Cidade_ID"      NUMBER(10) NOT NULL,
  CONSTRAINT "Cidades_PRIMARY" PRIMARY KEY ("Cidade_ID")
);

CREATE TABLE "Gerentes" (
  "Gerente"    NVARCHAR2(255),
  "Gerente_ID" NUMBER(10) NOT NULL,
  CONSTRAINT "Gerentes_PRIMARY" PRIMARY KEY ("Gerente_ID")
);

CREATE TABLE "Clientes" (
  "Cliente_ID"      NUMBER(10) NOT NULL,
  "Cliente"         NVARCHAR2(255),
  "Cliente_Contato" NVARCHAR2(255),
  "Telefone"        NVARCHAR2(255),
  "Cidade_ID"       NUMBER(10) NOT NULL,
  CONSTRAINT "Clientes_PRIMARY" PRIMARY KEY ("Cliente_ID")
);

CREATE TABLE "Vendedores" (
  "Vendedor_ID"    NVARCHAR2(255) NOT NULL,
  "Vendedor"       NVARCHAR2(255),
  "Vendedor_Sexo"  NVARCHAR2(255),
  "Cidade_ID"      NUMBER(10) NOT NULL,
  "Gerente_ID"     NUMBER(10) NOT NULL,
  CONSTRAINT "Vendedores_PRIMARY" PRIMARY KEY ("Vendedor_ID")
);

CREATE TABLE "Produtos" (
  "Produto_Code"       NUMBER(10) NOT NULL,
  "Produto_Referencia" NVARCHAR2(100),
  "Produto"            NVARCHAR2(100),
  "Categoria_ID"       NUMBER(10),
  CONSTRAINT "Produtos_PRIMARY" PRIMARY KEY ("Produto_Code")
);

CREATE TABLE "Pedidos" (
  "Pedido_ID"    NUMBER(10) NOT NULL,
  "Cliente_ID"   NUMBER(10) NOT NULL,
  "Vendedor_ID"  NVARCHAR2(255) NOT NULL,
  "Data_Venda"   DATE,
  "Meta_ID"      NVARCHAR2(10),
  "Perc_Frete"   BINARY_DOUBLE,
  "Cancelado"    NUMBER(1) DEFAULT 0 NOT NULL,
  "Data_Remessa" DATE,
  "Periodo"      DATE NOT NULL,
  CONSTRAINT "Pedidos_PRIMARY" PRIMARY KEY ("Pedido_ID")
);

CREATE TABLE "PedItem" (
  "PedItem_ID"    NUMBER(10) NOT NULL,
  "Pedido_ID"     NUMBER(10) NOT NULL,
  "Produto_ID"    NUMBER(10) NOT NULL,
  "Qtde_Venda"    NUMBER(10),
  "Valor_Venda"   BINARY_DOUBLE,
  "Valor_Custo"   BINARY_DOUBLE,
  "Valor_Frete"   BINARY_DOUBLE,
  "Valor_Margem"  BINARY_DOUBLE,
  "PrecoUN_Venda" BINARY_DOUBLE,
  "PrecoUN_Custo" BINARY_DOUBLE,
  CONSTRAINT "PedItem_PRIMARY" PRIMARY KEY ("PedItem_ID")
);

CREATE TABLE "Devolucoes" (
  "Devolucao_ID"   NUMBER(10) NOT NULL,
  "Pedido_ID"      NUMBER(10) NOT NULL,
  "Data_Devolucao" DATE DEFAULT TRUNC(SYSDATE) NOT NULL,
  "Observacao"     NVARCHAR2(500),
  CONSTRAINT "Devolucoes_PRIMARY" PRIMARY KEY ("Devolucao_ID")
);

CREATE TABLE "Devolucao_Item" (
  "Devolucao_Item_ID" NUMBER(10) NOT NULL,
  "Devolucao_ID"       NUMBER(10) NOT NULL,
  "PedItem_ID"         NUMBER(10) NOT NULL,
  "Produto_ID"         NUMBER(10) NOT NULL,
  "Qtde_Devolvida"     NUMBER(10) NOT NULL,
  "PrecoUN_Venda"      NUMBER(10,2) NOT NULL,
  "Valor_Devolucao"    NUMBER(10,2),
  CONSTRAINT "Devolucao_Item_PRIMARY" PRIMARY KEY ("Devolucao_Item_ID")
);

CREATE TABLE "TabFrete" (
  "Cidade_ID"  NUMBER(10) NOT NULL,
  "Periodo"    DATE NOT NULL,
  "Perc_Frete" BINARY_DOUBLE,
  CONSTRAINT "TabFrete_PRIMARY" PRIMARY KEY ("Cidade_ID", "Periodo")
);

CREATE TABLE "TabPreco" (
  "Produto_ID"    NUMBER(10) NOT NULL,
  "Periodo"       DATE NOT NULL,
  "PrecoUN_Venda" BINARY_DOUBLE,
  "PrecoUN_Custo" BINARY_DOUBLE,
  CONSTRAINT "TabPreco_PRIMARY" PRIMARY KEY ("Produto_ID", "Periodo")
);


-- ============================================================================
-- 2. FOREIGN KEYS (15) — mesmos nomes usados no MySQL de origem
-- ============================================================================
ALTER TABLE "Categoria"      ADD CONSTRAINT "FKCategoriaDepartamento"  FOREIGN KEY ("Departamento_ID") REFERENCES "Departamento" ("Departamento_ID");
ALTER TABLE "Clientes"       ADD CONSTRAINT "FKClienteCidades"         FOREIGN KEY ("Cidade_ID")       REFERENCES "Cidades" ("Cidade_ID");
ALTER TABLE "Devolucao_Item" ADD CONSTRAINT "FKDevolucaoItemDevolucao" FOREIGN KEY ("Devolucao_ID")    REFERENCES "Devolucoes" ("Devolucao_ID");
ALTER TABLE "Devolucao_Item" ADD CONSTRAINT "FKDevolucaoItemPedItem"   FOREIGN KEY ("PedItem_ID")      REFERENCES "PedItem" ("PedItem_ID");
ALTER TABLE "Devolucao_Item" ADD CONSTRAINT "FKDevolucaoItemProduto"   FOREIGN KEY ("Produto_ID")      REFERENCES "Produtos" ("Produto_Code");
ALTER TABLE "Devolucoes"     ADD CONSTRAINT "FKDevolucaoPedido"        FOREIGN KEY ("Pedido_ID")       REFERENCES "Pedidos" ("Pedido_ID");
ALTER TABLE "PedItem"        ADD CONSTRAINT "FKPedItemPedido"          FOREIGN KEY ("Pedido_ID")       REFERENCES "Pedidos" ("Pedido_ID");
ALTER TABLE "PedItem"        ADD CONSTRAINT "FKPedItemProduto"         FOREIGN KEY ("Produto_ID")      REFERENCES "Produtos" ("Produto_Code");
ALTER TABLE "Pedidos"        ADD CONSTRAINT "FKPedidoCliente"          FOREIGN KEY ("Cliente_ID")      REFERENCES "Clientes" ("Cliente_ID");
ALTER TABLE "Pedidos"        ADD CONSTRAINT "FKPedidoVendedor"         FOREIGN KEY ("Vendedor_ID")     REFERENCES "Vendedores" ("Vendedor_ID");
ALTER TABLE "Produtos"       ADD CONSTRAINT "FKProdutoCategoria"       FOREIGN KEY ("Categoria_ID")    REFERENCES "Categoria" ("Categoria_ID");
ALTER TABLE "TabFrete"       ADD CONSTRAINT "FKTabFreteCidade"         FOREIGN KEY ("Cidade_ID")       REFERENCES "Cidades" ("Cidade_ID");
ALTER TABLE "TabPreco"       ADD CONSTRAINT "FKTabPrecoProduto"        FOREIGN KEY ("Produto_ID")      REFERENCES "Produtos" ("Produto_Code");
ALTER TABLE "Vendedores"     ADD CONSTRAINT "FKVendedorCidade"         FOREIGN KEY ("Cidade_ID")       REFERENCES "Cidades" ("Cidade_ID");
ALTER TABLE "Vendedores"     ADD CONSTRAINT "FKVendedorGerente"        FOREIGN KEY ("Gerente_ID")      REFERENCES "Gerentes" ("Gerente_ID");


-- ============================================================================
-- 3. AUTO INCREMENT -> SEQUENCE + TRIGGER (equivalente ao AUTO_INCREMENT)
--    O trigger so gera valor quando a coluna vem NULL/omitida no INSERT,
--    permitindo cargas iniciais/CDC com ID explicito.
-- ============================================================================
CREATE SEQUENCE "SEQ_DEVOLUCOES_ID" START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE "SEQ_DEVOLUCAO_ITEM_ID" START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER "TRG_DEVOLUCOES_ID"
  BEFORE INSERT ON "Devolucoes"
  FOR EACH ROW
  WHEN (NEW."Devolucao_ID" IS NULL)
BEGIN
  :NEW."Devolucao_ID" := "SEQ_DEVOLUCOES_ID".NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER "TRG_DEVOLUCAO_ITEM_ID"
  BEFORE INSERT ON "Devolucao_Item"
  FOR EACH ROW
  WHEN (NEW."Devolucao_Item_ID" IS NULL)
BEGIN
  :NEW."Devolucao_Item_ID" := "SEQ_DEVOLUCAO_ITEM_ID".NEXTVAL;
END;
/


-- ============================================================================
-- 4. UNIQUE / CHECK constraints (existiam no MySQL de origem)
-- ============================================================================
ALTER TABLE "Devolucao_Item" ADD CONSTRAINT "UKDevolucaoItem" UNIQUE ("Devolucao_ID", "PedItem_ID");
ALTER TABLE "Devolucao_Item" ADD CONSTRAINT "CHKQtdeDevolvida" CHECK ("Qtde_Devolvida" > 0);


-- ============================================================================
-- 5. Coluna calculada (MySQL: GENERATED ALWAYS AS (...) STORED)
--    Valor_Devolucao = Qtde_Devolvida * PrecoUN_Venda
-- ============================================================================
CREATE OR REPLACE TRIGGER "TRG_DEVOLUCAO_ITEM_VALOR"
  BEFORE INSERT OR UPDATE OF "Qtde_Devolvida", "PrecoUN_Venda" ON "Devolucao_Item"
  FOR EACH ROW
BEGIN
  :NEW."Valor_Devolucao" := :NEW."Qtde_Devolvida" * :NEW."PrecoUN_Venda";
END;
/

-- Pedidos.Periodo = primeiro dia do mes de Data_Venda (MySQL: DEFAULT calculado).
-- Oracle nao aceita DEFAULT referenciando outra coluna -> trigger.
CREATE OR REPLACE TRIGGER "TRG_PEDIDOS_PERIODO"
  BEFORE INSERT OR UPDATE OF "Data_Venda" ON "Pedidos"
  FOR EACH ROW
  WHEN (NEW."Data_Venda" IS NOT NULL)
BEGIN
  :NEW."Periodo" := TRUNC(:NEW."Data_Venda", 'MM');
END;
/

COMMIT;
