# Guia de Instalação — Projeto VendasODS

> Este guia assume que os pré-requisitos já foram atendidos — ver [Guia_Implementacao_Novo_Tenant.md](Guia_Implementacao_Novo_Tenant.md) antes de seguir os passos abaixo (licenciamento do tenant, papéis de usuário, gateway, bucket S3, ambiente com Git/`qlik-cli`/MCP configurados).

---

## Visão geral da sequência

1. Preparar o ambiente local (Git, `qlik-cli`, MCP)
2. *(manual)* Instalar e registrar o Data Movement Gateway
3. Criar os Spaces
4. Criar as conexões de dados
5. Importar o projeto de Data Integration (CDC)
6. Criar os apps e carregar os scripts
7. Construir o conteúdo analítico do `viz001` (via MCP)
8. Importar e ajustar a Automation
9. Validar

---

## 1. Preparar o ambiente local

```
git clone https://github.com/pedrobergo/Qlik_IADataEngineering.git
qlik context create <nome-do-contexto> --server https://<tenant-novo>.qlikcloud.com --api-key <api-key>
qlik context use <nome-do-contexto>
```

Registrar o servidor MCP Qlik apontando para o mesmo tenant (ex. via `claude mcp add`), autenticado com a mesma API key.

## 2. Instalar e registrar o Data Movement Gateway *(manual)*

Baixar o instalador no tenant novo (Management Console → Data Gateways), instalar no host preparado (rede até o Oracle fonte) e registrar com um nome de referência, ex. `QDMG_VendasODS`. Este passo não pode ser feito pelo Claude — exige rodar um instalador em uma máquina física/VM específica.

## 3. Criar os Spaces

- **Data space**: `VendasODS_Data` (conexões/objetos de Data Integration)
- **Shared space**: `VendasODS_Shared` (apps, conexões de analytics, Automation)

## 4. Criar as conexões de dados

| Nome | Tipo | Space | Detalhe |
|---|---|---|---|
| `di-oracle` | Fonte (Data Integration) | `VendasODS_Data` | Server `<host>:1521/<service>`, schema `VENDASODS`, via `QDMG_VendasODS` |
| `di-s3` | Destino (Data Integration) | `VendasODS_Data` | Amazon S3, par de chaves, bucket novo |
| `da-s3` | Storage (Analytics) | `VendasODS_Shared` | `File_AmazonS3ConnectorV2`, mesmo bucket, usado pelos apps para ler/gravar parquet |
| `da-s3-metadata` | Storage/ListObjects (Analytics) | `VendasODS_Shared` | `AmazonS3ConnectorV2`, usado para listagem de objetos |

> Nota do script `str001`: o conector S3 V2 não suporta wildcard em `LOAD FROM`/`FILELIST()`. O padrão usado é listar o bucket inteiro via `da-s3-metadata` com `prefix=''`, manter em memória, e filtrar do lado do Qlik com `LIKE`. Validar se esse comportamento se repete no tenant novo antes de assumir que o workaround ainda é necessário.

## 5. Importar o projeto de Data Integration (CDC)

O projeto já existe como template exportado em [data-integration/P01_VendasODS_S3/](data-integration/P01_VendasODS_S3/) (formato QTCP, tarefa `vendasods-susp`, tipo `LAKE_LANDING`, CDC `PERIODIC` a cada 60s, saída Parquet) — não é recriado manualmente:

```
qlik di-project import --file data-integration/P01_VendasODS_S3 ...
```

Antes do import, ajustar [bindings.json](data-integration/P01_VendasODS_S3/bindings.json) com os IDs das conexões criadas no passo 4:

| Variável | Valor de referência | Ajustar para |
|---|---|---|
| `task.vendasods-susp.sourceConnection` | `{{id(connection, VendasODS_Data.di-oracle)}}` | ID da conexão `di-oracle` do tenant novo |
| `task.vendasods-susp.targetConnection` | `{{id(connection, VendasODS_Data.di-s3)}}` | ID da conexão `di-s3` do tenant novo |
| `task.vendasods-susp.folder` | `materlake/landing` | Manter (prefixo esperado por `str001`) |
| `...VENDASODS.schema(Pattern)` | `VENDASODS` | Schema Oracle do ambiente novo |

Tabelas replicadas: `Cidades, Categoria, Clientes, Departamento, Devolucao_Item, Devolucoes, Gerentes, PedItem, Pedidos, Produtos, TabFrete, TabPreco, Vendedores`.

## 6. Criar os apps e carregar os scripts

Criar os 7 apps no space `VendasODS_Shared` e carregar os scripts, na ordem abaixo (respeita a dependência Bronze → Silver → Gold → Analytics), rodando reload inicial de cada um antes de seguir para o próximo:

| Ordem | App | Script fonte |
|---|---|---|
| 1 | str001_bronze_vendasods | [scripts/str001_bronze_vendasods.qvs](scripts/str001_bronze_vendasods.qvs) |
| 2 | trf001_silver_vendasods | [scripts/trf001_silver_vendasods.qvs](scripts/trf001_silver_vendasods.qvs) |
| 3 | trf002_silver_devolucoes | [scripts/trf002_silver_devolucoes.qvs](scripts/trf002_silver_devolucoes.qvs) |
| 4 | trf003_silver_vendas | [scripts/trf003_silver_vendas.qvs](scripts/trf003_silver_vendas.qvs) |
| 5 | trf004_silver_devolucoes_consolidado | [scripts/trf004_silver_devolucoes_consolidado.qvs](scripts/trf004_silver_devolucoes_consolidado.qvs) |
| 6 | trf005_gold_star_schema | [scripts/trf005_gold_star_schema.qvs](scripts/trf005_gold_star_schema.qvs) |
| 7 | viz001_vendasods_analytics | [scripts/viz001_vendasods_analytics.qvs](scripts/viz001_vendasods_analytics.qvs) |

Não recriar os scripts `ext001-3` — são legado, substituídos por `str001`.

## 7. Conteúdo analítico do `viz001` (via MCP)

Construir sheets, gráficos e master items (dimensões/medidas) usando as ferramentas MCP (`qlik_create_sheet`, `qlik_add_chart`, `qlik_create_dimension`, `qlik_create_measure`, etc.) — não coberto pelo `qlik-cli`. Se o projeto usar catálogo/data products/glossário, registrar aqui também (`qlik_create_data_product`, `qlik_create_glossary_term`, etc.).

## 8. Importar e ajustar a Automation

Importar/recriar a partir de [automation/VendasODS_Pipeline_Execution.json](automation/VendasODS_Pipeline_Execution.json), ajustando:
- Os 7 `snippet_guid` (Do Reload) para os **novos App IDs** criados no passo 6
- O `spaceId` para o novo `VendasODS_Shared`
- Autorizar a conexão OAuth do conector "Qlik Cloud Services" dentro do editor da Automation, com um usuário que tenha permissão de reload nos 7 apps
- Revisar o schedule (`RRULE:FREQ=MINUTELY;INTERVAL=15`, timezone `America/Sao_Paulo`) e `maxConcurrentRuns: 1`
- Detalhes completos: [automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md](automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md)

## 9. Validação / smoke test

- [ ] Tarefa CDC do Data Integration rodando e gravando arquivos em `materlake/landing/` no bucket novo
- [ ] Reload manual de `str001` conclui sem erro e grava `materlake/bronze/*.parquet`
- [ ] Reload manual de `trf001`→`trf005` conclui em cascata sem erro
- [ ] `viz001` reload conclui e as visualizações exibem dados
- [ ] Rodar a Automation manualmente uma vez (`qlik automation run create`) e conferir `status: finished` sem erro em nenhuma etapa
- [ ] Confirmar que o schedule da Automation dispara sozinho na frequência esperada

Depois de validado, atribuir papéis (`producer`/`codeveloper`/`consumer`) aos usuários finais nos espaços — ver [Guia_Implementacao_Novo_Tenant.md](Guia_Implementacao_Novo_Tenant.md#5-papéis-nos-espaços-pós-implementação).

---

## Padrões de nomenclatura a seguir durante a instalação

Ao criar/nomear objetos (scripts, tasks, conexões, pastas), seguir os padrões abaixo:

1. Scripts de Qlik Data Analytics (qvs, qvw, qvf, dfw, etc.):
   1. Nome prefixado pelo objetivo
      1. 'ext' para extração de dados,
      1. 'trf' para transformação de dados
      1. 'viz' para visualização de dados
      1. 'gen' para scripts genéricos
      1. 'str' para scripts de armazenamento (storage)
   1. Nome sufixado por uma ação numerada, ex.: 'ext001', 'ext002', 'trf001', 'trf002'
   1. A descrição deve ter uma explicação completa com propósito e contexto envolvido
   1. Marcado (tagged) com o objetivo, como 'Extract', 'Transform', 'Load', 'Generic' e o Goal do projeto --> O goal deste projeto é 'VendasODS'
1. Projetos de Qlik Data Integration
   1. Nome prefixado pela constante 'PRJ'
   1. Nome sufixado por uma ação numerada, ex.: 'prj001', 'prj002'
   1. A descrição deve ter uma explicação completa com propósito e contexto envolvido
   1. Marcado (tagged) com o Goal do projeto --> O goal deste projeto é 'VendasODS'
1. Tasks de Qlik Data Integration
   1. Nome sufixado pelo objetivo
      1. 'ext' para extração de dados,
      1. 'trf' para transformação de dados
      1. 'gen' para tasks genéricas
   1. Nome sufixado por uma ação numerada, ex.: 'ext001', 'ext002', 'trf001', 'trf002'
   1. A descrição deve ter uma explicação completa com propósito e contexto envolvido
1. Conexões de Dados
   1. O nome das conexões de dados deve ser prefixado pela seção Qlik, como
      1. 'da' para Data Analytics
      1. 'di' para Data Integration
   1. Sufixado pelo tipo
      1. 'mysql' para banco de dados MySQL
      1. 'oracle' para banco de dados Oracle
      1. 's3' para banco de dados Amazon S3
      1. 'adls' para Azure Data Lake Storage
      1. 'sqlsrv' para banco de dados SQL Server
1. Arquitetura Medalhão
   1. Os arquivos da camada Landing devem ser armazenados em uma pasta chamada 'landing'
      1. Landing é baseada nas origens, então utilize uma subpasta com o nome da origem: 'vendasods'. Se uma nova origem for adicionada, utilize seu nome como nome de subpasta.
      1. Landing é uma área de armazenamento transitória, portanto pode ser removida a qualquer momento.
   1. Os arquivos da camada Bronze devem ser armazenados em uma pasta chamada 'bronze'
      1. Bronze é baseada nas origens, então utilize uma subpasta com o nome da origem: 'vendasods'. Se uma nova origem for adicionada, utilize seu nome como nome de subpasta.
      1. Bronze é uma área de armazenamento persistente de longo prazo, portanto todas as tasks devem adicionar dados a ela de forma incremental.
   1. Os arquivos da camada Silver devem ser armazenados em uma pasta chamada 'silver'
      1. Subpasta é importante para armazenar mais de um conjunto de arquivos, resultante de múltiplas transformações em sequência, então utilize sufixo numérico, como silver/silver001, silver/silver002, silver/silver003
      1. Silver é uma área de armazenamento persistente de longo prazo, portanto todas as tasks devem adicionar dados a ela de forma incremental.
   1. Camada Gold:
      1. A pasta de arquivos deve se chamar 'gold'
      1. Dimensões prefixadas por 'dim_'
      1. Tabelas de fato prefixadas por 'fact_'
      1. Prefixo dos nomes de campo:
         1. Chaves: 'key_'
         1. Flags: 'flg_' exemplos: 'flg_cancel', 'flg_deleted'
         1. Numérico: 'nm_'
         1. Texto: 'str_'
         1. Outros: 'gen_' para uso genérico
      1. Gold é uma área de armazenamento persistente de longo prazo, portanto todas as tasks devem adicionar dados a ela de forma incremental.
