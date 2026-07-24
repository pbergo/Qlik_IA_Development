# Guia de Instalação — Projeto VendasODS

> Este guia assume que os pré-requisitos já foram atendidos — ver [Guia_Implementacao_Novo_Tenant.md](Guia_Implementacao_Novo_Tenant.md) antes de seguir os passos abaixo (licenciamento do tenant, papéis de usuário, gateway, bucket S3, ambiente com `qlik-cli`/MCP configurados e os arquivos do projeto disponíveis localmente — via Git ou download ZIP).

---

## Visão geral da sequência

1. Preparar o ambiente local (`qlik-cli`, MCP)
2. Preparar a fonte Oracle (usuário, tabelas e dados de exemplo)
3. *(manual)* Instalar e registrar o Data Movement Gateway
4. Criar os Spaces
5. Criar as conexões de dados (`di-oracle`/`di-s3` *manual*, ver nota no passo 5)
6. Importar o projeto de Data Integration (CDC)
7. Criar os apps e carregar os scripts
8. Construir o conteúdo analítico do `viz001` (via MCP)
9. Importar e ajustar a Automation
10. Validar

---

## 1. Preparar o ambiente local

Obter os arquivos do projeto por uma das duas formas (o restante do guia não depende de qual foi usada):

- **Git** (mantém histórico e facilita `git pull` de atualizações futuras): `git clone https://github.com/pedrobergo/Qlik_IADataEngineering.git`
- **Download ZIP** (não exige Git instalado): baixar o ZIP do repositório (GitHub → Code → Download ZIP) e extrair localmente

```
qlik context create <nome-do-contexto> --server https://<tenant-novo>.qlikcloud.com --api-key <api-key>
qlik context use <nome-do-contexto>
```

Registrar o servidor MCP Qlik apontando para o mesmo tenant. Em ambiente VS Code + conta claude.ai (caminho testado em deploy real), isso é feito via **conector personalizado nas configurações do claude.ai** (não pela CLI `claude mcp add`) — e exige reiniciar o VS Code para o conector aparecer disponível. Passo a passo detalhado: [Guia_Implementacao_Novo_Tenant.md §2.7](Guia_Implementacao_Novo_Tenant.md#27-integração-mcp-configurada).

> Ver [Guia_Implementacao_Novo_Tenant.md §4](Guia_Implementacao_Novo_Tenant.md#4-segredos-e-credenciais-a-preparar-checklist) para a prática recomendada de coletar as credenciais (API key, senha do Oracle, chaves do S3) uma única vez no início e registrá-las em [secrets/secrets.env](secrets/secrets.env).

## 2. Preparar a fonte Oracle (usuário, tabelas e dados de exemplo)

Antes de instalar o gateway e criar a conexão `di-oracle`, o schema `VENDASODS` precisa existir no Oracle fonte com a estrutura e (opcionalmente) os dados de exemplo deste projeto. Se ainda não há uma instância Oracle disponível, ver [Apêndice A.1](#a1-banco-de-dados-oracle-container-oracle-xe) para subir uma via Docker. Os scripts estão em [base-dados/](base-dados/) e devem rodar nesta ordem:

| Ordem | Script | O que faz | Executar como |
|---|---|---|---|
| 1 | [base-dados/oracle_instance_cdc_prereqs_vendasods.sql](base-dados/oracle_instance_cdc_prereqs_vendasods.sql) | Habilita supplemental logging mínimo (online) e verifica/orienta habilitar o modo **ARCHIVELOG** (interativo, derruba conexões) — pré-requisitos de **instância** para o LogMiner do Data Movement Gateway, fora do escopo dos scripts seguintes | `sysdba` (ex. `sqlplus sys/<senha>@//<host>:<porta>/<service> as sysdba`) |
| 2 | [base-dados/cdc_config_vendasods.sql](base-dados/cdc_config_vendasods.sql) | Cria o usuário `vendasods` e concede os grants exigidos pelo conector Oracle do Data Movement Gateway (leitura de redo log/LogMiner, dicionário de dados) + os grants de DDL (`CREATE ANY TABLE`, `CREATE TRIGGER`, `CREATE SEQUENCE`, etc.) usados pelo script seguinte | Usuário com privilégio de `GRANT` (ex. `system`) |
| 3 | [base-dados/create_database_vendasods.sql](base-dados/create_database_vendasods.sql) | Cria as 13 tabelas, as 15 Foreign Keys, o auto increment (`SEQUENCE` + `TRIGGER`, equivalente ao `AUTO_INCREMENT` da origem MySQL legada) e as demais constraints (`UNIQUE`, `CHECK`) | `vendasods` |
| 4 | [base-dados/vendasods_oracle_data.sql](base-dados/vendasods_oracle_data.sql) | Popula as tabelas com uma cópia dos dados de exemplo (`INSERT INTO`, ~253 mil linhas, já na ordem que respeita as FKs) | `vendasods` |

> Nota: `ALTER TABLE ... MODIFY ... AS IDENTITY` não funciona para converter uma coluna já existente em identity nativo do Oracle (`ORA-30673`, mesmo em tabela vazia) — por isso o auto increment usa o padrão clássico `SEQUENCE` + `TRIGGER`. Ver comentários no próprio `create_database_vendasods.sql`.

> **Sobre o script 1 (pré-requisitos de instância)**: o trecho de supplemental logging é seguro de rodar direto (operação online). Já o bloco de ARCHIVELOG **deve ser executado interativamente**, linha a linha, em uma sessão `sqlplus` local/direta no host do banco — o `SHUTDOWN`/`STARTUP` derruba todas as conexões da instância, então não deve ser disparado por uma ferramenta remota automatizada. Erro observado em deploy real quando o supplemental logging não estava habilitado: `[SOURCE_UNLOAD]E: Minimal database supplemental logging level is not enabled [1020418]`.

## 3. Instalar e registrar o Data Movement Gateway *(manual)*

Baixar o instalador no tenant novo (Management Console → Data Gateways), instalar no host preparado (rede até o Oracle fonte) e registrar com um nome de referência, ex. `QDMG_VendasODS`. Alternativa via Docker: ver [Apêndice A.2](#a2-data-movement-gateway-container). Em ambos os casos, o passo de colar a chave de registro na Management Console é manual — não pode ser feito pelo Claude (exige acesso interativo ao navegador/console).

## 4. Criar os Spaces

- **Data space**: `VendasODS_Data` (conexões/objetos de Data Integration)
- **Shared space**: `VendasODS_Shared` (apps, conexões de analytics, Automation)

## 5. Criar as conexões de dados

| Nome | Tipo | Space | Detalhe | Criação |
|---|---|---|---|---|
| `di-oracle` | Fonte (Data Integration) | `VendasODS_Data` | Server `<host>:1521/<service>`, schema `VENDASODS`, via `QDMG_VendasODS` | **Manual (UI)** |
| `di-s3` | Destino (Data Integration) | `VendasODS_Data` | Amazon S3, par de chaves, bucket novo | **Manual (UI)** |
| `da-s3` | Storage (Analytics) | `VendasODS_Shared` | `File_AmazonS3ConnectorV2`, mesmo bucket, usado pelos apps para ler/gravar parquet | `qlik-cli`/API |
| `da-s3-metadata` | Storage/ListObjects (Analytics) | `VendasODS_Shared` | `AmazonS3ConnectorV2`, usado para listagem de objetos | `qlik-cli`/API |

> Nota do script `str001`: o conector S3 V2 não suporta wildcard em `LOAD FROM`/`FILELIST()`. O padrão usado é listar o bucket inteiro via `da-s3-metadata` com `prefix=''`, manter em memória, e filtrar do lado do Qlik com `LIKE`. Validar se esse comportamento se repete no tenant novo antes de assumir que o workaround ainda é necessário.

> **As duas conexões `di-*` são manuais** *(assim como o item 3, instalação do gateway)*: tanto `di-oracle` quanto `di-s3` precisam ser criadas pelo usuário via UI — Management Console/Hub → seção **Data Integration → Connections** (não **Data Analytics**, que é onde ficam as conexões `da-*`, essas sim automatizáveis via `qlik-cli`/API). Não podem ser feitas pelo Claude via `qlik-cli`/API.

## 6. Importar o projeto de Data Integration (CDC)

O projeto já existe como template exportado em [../projeto/data-integration/P01_VendasODS_S3/](../projeto/data-integration/P01_VendasODS_S3/) (formato QTCP, tarefa `vendasods-susp`, tipo `LAKE_LANDING`, CDC `PERIODIC` a cada 60s, saída Parquet) — não é recriado manualmente:

```
qlik di-project import --file projeto/data-integration/P01_VendasODS_S3 ...
```

Antes do import, ajustar [bindings.json](../projeto/data-integration/P01_VendasODS_S3/bindings.json) com os IDs das conexões criadas no passo 5:

| Variável | Valor de referência | Ajustar para |
|---|---|---|
| `task.vendasods-susp.sourceConnection` | `{{id(connection, VendasODS_Data.di-oracle)}}` | ID da conexão `di-oracle` do tenant novo |
| `task.vendasods-susp.targetConnection` | `{{id(connection, VendasODS_Data.di-s3)}}` | ID da conexão `di-s3` do tenant novo |
| `task.vendasods-susp.folder` | `datalake/landing` | Manter (prefixo esperado por `str001`) |
| `...VENDASODS.schema(Pattern)` | `VENDASODS` | Schema Oracle do ambiente novo |

Tabelas replicadas: `Cidades, Categoria, Clientes, Departamento, Devolucao_Item, Devolucoes, Gerentes, PedItem, Pedidos, Produtos, TabFrete, TabPreco, Vendedores`.

## 7. Criar os apps e carregar os scripts

Criar os 7 apps no space `VendasODS_Shared` e carregar os scripts, na ordem abaixo (respeita a dependência Bronze → Silver → Gold → Analytics), rodando reload inicial de cada um antes de seguir para o próximo:

| Ordem | App | Script fonte |
|---|---|---|
| 1 | str001_bronze_vendasods | [../projeto/scripts/str001_bronze_vendasods.qvs](../projeto/scripts/str001_bronze_vendasods.qvs) |
| 2 | trf001_silver_vendasods | [../projeto/scripts/trf001_silver_vendasods.qvs](../projeto/scripts/trf001_silver_vendasods.qvs) |
| 3 | trf002_silver_devolucoes | [../projeto/scripts/trf002_silver_devolucoes.qvs](../projeto/scripts/trf002_silver_devolucoes.qvs) |
| 4 | trf003_silver_vendas | [../projeto/scripts/trf003_silver_vendas.qvs](../projeto/scripts/trf003_silver_vendas.qvs) |
| 5 | trf004_silver_devolucoes_consolidado | [../projeto/scripts/trf004_silver_devolucoes_consolidado.qvs](../projeto/scripts/trf004_silver_devolucoes_consolidado.qvs) |
| 6 | trf005_gold_star_schema | [../projeto/scripts/trf005_gold_star_schema.qvs](../projeto/scripts/trf005_gold_star_schema.qvs) |
| 7 | viz001_vendasods_analytics | [../projeto/scripts/viz001_vendasods_analytics.qvs](../projeto/scripts/viz001_vendasods_analytics.qvs) |

Não recriar os scripts `ext001-3` — são legado, substituídos por `str001`.

## 8. Conteúdo analítico do `viz001` (via MCP)

Construir sheets, gráficos e master items (dimensões/medidas) usando as ferramentas MCP (`qlik_create_sheet`, `qlik_add_chart`, `qlik_create_dimension`, `qlik_create_measure`, etc.) — não coberto pelo `qlik-cli`. Se o projeto usar catálogo/data products/glossário, registrar aqui também (`qlik_create_data_product`, `qlik_create_glossary_term`, etc.).

## 9. Importar e ajustar a Automation

Importar/recriar a partir de [../projeto/automation/VendasODS_Pipeline_Execution.json](../projeto/automation/VendasODS_Pipeline_Execution.json), ajustando:
- Os 7 `snippet_guid` (Do Reload) para os **novos App IDs** criados no passo 7
- O `spaceId` para o novo `VendasODS_Shared`
- Autorizar a conexão OAuth do conector "Qlik Cloud Services" dentro do editor da Automation, com um usuário que tenha permissão de reload nos 7 apps *(verificar se é realmente necessário neste ambiente — ver nota abaixo)*
- Revisar o schedule (`RRULE:FREQ=MINUTELY;INTERVAL=15`, timezone `America/Sao_Paulo`) e `maxConcurrentRuns: 1`
- Detalhes completos: [../projeto/automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md](../projeto/automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md)

> **Nota sobre a autorização OAuth (achado em deploy real, 2026-07-23)**: neste ambiente a Automation rodou com sucesso já no primeiro disparo agendado, sem exigir nenhuma autorização OAuth manual no editor. Não está confirmado se isso vale sempre (pode depender de o usuário/credencial já estar previamente autorizado no espaço, do tipo de autenticação, ou de outra condição não identificada). Tratar o passo acima como **algo a verificar**, não como bloqueante garantido — só seguir o passo manual de autorização se a Automation efetivamente falhar por falta dela.

## 10. Validação / smoke test

- [ ] Schema `VENDASODS` no Oracle fonte com as 13 tabelas, FKs e dados de exemplo (scripts do passo 2 rodaram sem erro)
- [ ] Supplemental logging mínimo e modo ARCHIVELOG habilitados na instância Oracle (ver nota no passo 2) — sem isso a tarefa CDC falha com `ORA...1020418 Minimal database supplemental logging level is not enabled`
- [ ] Tarefa CDC do Data Integration rodando e gravando arquivos em `datalake/landing/` no bucket novo (full load inicial)
- [ ] **CDC incremental de fato capturando mudanças** (não só o full load): fazer um INSERT/UPDATE/DELETE de teste em uma tabela do schema `VENDASODS` na fonte Oracle e confirmar que a tarefa reflete isso — `totalProcessedCount` (ou métrica equivalente) da tarefa sai de 0/estável e um novo arquivo de mudança aparece em `datalake/landing/vendasods.<Tabela>__ct/`. Achado em deploy real (2026-07-23): o full load funcionou, mas nenhuma mudança incremental tinha sido processada (`totalProcessedCount: 0`) até essa checagem ser feita — sem ela, um CDC "travado" pode passar despercebido. Ferramenta pronta para gerar esse tráfego de teste: [../projeto/scripts/GenerateData.py](../projeto/scripts/GenerateData.py) (menu "2. Atualiza CDC", "3. Atualizar Data Remessa", "4. Cancelar Pedidos", "5. Gera Devoluções", "7. Apagar Registros" — cobrem INSERT/UPDATE/DELETE contra o schema `vendasods` via `oracledb`).
- [ ] Reload manual de `str001` conclui sem erro e grava `datalake/bronze/*.parquet`
- [ ] Reload manual de `trf001`→`trf005` conclui em cascata sem erro
- [ ] `viz001` reload conclui e as visualizações exibem dados
- [ ] Rodar a Automation manualmente uma vez (`qlik automation run create`) e conferir `status: finished` sem erro em nenhuma etapa
- [ ] Confirmar que o schedule da Automation dispara sozinho na frequência esperada

Depois de validado, atribuir papéis (`producer`/`codeveloper`/`consumer`) aos usuários finais nos espaços — ver [Guia_Implementacao_Novo_Tenant.md](Guia_Implementacao_Novo_Tenant.md#5-papéis-nos-espaços-pós-implementação).

---

## Apêndice A: Infraestrutura via Docker (opcional)

Passos opcionais para quem ainda não tem a infraestrutura pronta (Oracle fonte, gateways) e quer subir tudo localmente via container em vez de usar um ambiente já existente.

### A.1 Banco de dados Oracle (container `oracle-xe`)

Usado para o passo 2 ("Preparar a fonte Oracle") quando não há uma instância Oracle já disponível. Imagem recomendada: [`gvenzl/oracle-xe`](https://hub.docker.com/r/gvenzl/oracle-xe) (mantenedor de referência da comunidade Oracle, wrapper Apache-2.0 em cima do Oracle Database XE oficial — não exige login/`docker login`, diferente do registry oficial `container-registry.oracle.com/database/express`). O PDB padrão dessa imagem é **`XEPDB1`**, que já é o service name assumido em [../implantacao/data-connections/di-oracle.md](../implantacao/data-connections/di-oracle.md) e nos scripts de [base-dados/](base-dados/) — não precisa ajustar nada nos scripts do passo 2.

```
mkdir C:\qlikfolder\oracle-xe
docker run -d --name oracle-xe-vendasods -p 1521:1521 ^
  -e ORACLE_PASSWORD=<senha-do-SYS-SYSTEM> ^
  -v C:\qlikfolder\oracle-xe:/opt/oracle/oradata ^
  gvenzl/oracle-xe
```

- `-v` monta um volume local para persistir os data files entre restarts do container (sem isso, os dados somem se o container for removido).
- Acompanhar o boot (a primeira inicialização demora alguns minutos, criando o PDB): `docker logs -f oracle-xe-vendasods` até aparecer `DATABASE IS READY TO USE!`.
- Testar a conexão: `sqlplus system/<senha>@//localhost:1521/XEPDB1`.
- Com o container pronto, seguir o passo 2 normalmente, na ordem da tabela: [oracle_instance_cdc_prereqs_vendasods.sql](base-dados/oracle_instance_cdc_prereqs_vendasods.sql) como `sys ... as sysdba` (a imagem `oracle-xe` não vem com supplemental logging nem ARCHIVELOG habilitados por padrão), depois [cdc_config_vendasods.sql](base-dados/cdc_config_vendasods.sql) como `system` (senha = `ORACLE_PASSWORD` definida acima) e por fim [create_database_vendasods.sql](base-dados/create_database_vendasods.sql) + [vendasods_oracle_data.sql](base-dados/vendasods_oracle_data.sql) como `vendasods`.

> Nota de licenciamento: o Oracle Database XE em si é gratuito, mas sujeito aos termos de licença da Oracle (Oracle Free Use Terms), aceitos implicitamente ao usar a imagem. Não é uma licença comercial completa do Oracle Database — adequado para dev/homologação/demo, não para produção com SLA.

### A.2 Data Movement Gateway (container)

Alternativa ao instalador RPM tradicional do passo 3, usando a imagem [`pedrobergo/qlikdatamovement`](https://github.com/pbergo/datamovement-docker) (**não é um projeto/imagem oficial suportado pela Qlik** — build de terceiro).

```
mkdir c:\qlikfolder\pbergo-qcda

docker run --name qdmg-pbergo-qcda -d ^
  -e QlikUpdateGateway=no ^
  -e QlikUpdateODBC=none ^
  -e QlikTenant="pbergo-qcda.us.qlikcloud.com" ^
  --mount type=bind,source=c:\qlikfolder\pbergo-qcda,target=/opt ^
  pedrobergo/qlikdatamovement
```

- `QlikUpdateGateway=no` — não atualiza o binário do gateway automaticamente no start do container.
- `QlikUpdateODBC=none` — não instala/atualiza drivers ODBC no start (evita provisionar drivers desnecessários no container).
- `QlikTenant` — URL do tenant de destino (`<tenant>.<região>.qlikcloud.com`). **Nota**: o README do repositório documenta essa variável como `QlikCloudTenant`, não `QlikTenant` — se o container subir e não conectar no tenant esperado, validar qual nome de variável a versão da imagem realmente espera antes de seguir.
- `--mount type=bind,source=c:\qlikfolder\pbergo-qcda,target=/opt` — persiste os dados/configuração do gateway (inclusive a chave de registro) no host, em `C:\qlikfolder\pbergo-qcda`.

**Obter a chave de registro** (gerada automaticamente no primeiro start). Duas formas equivalentes, já que `/opt` está montado em `c:\qlikfolder\pbergo-qcda`:

- De dentro do container: `docker exec -it qdmg-pbergo-qcda cat /opt/qlik/gateway/movement/data/qdmg_regkey.txt`
- Direto no host (sem precisar do `docker exec`): abrir `C:\qlikfolder\pbergo-qcda\qlik\gateway\movement\data\qdmg_regkey.txt`

Copiar todo o conteúdo entre `{ }`.

**Registrar no tenant** *(manual, via navegador)*:
1. Management Console → **Administration → Data gateways → Create**
2. Nome: `QDMG_VendasODS` (padrão usado no passo 3) — Tipo: **Data Movement**
3. Space: `VendasODS_Data` (criado no passo 4)
4. Colar a chave de registro no campo **Key** → Create
5. Aguardar alguns minutos e atualizar a página — status deve mudar para **Connected**. Se continuar **Disconnected**, verificar conectividade de saída do container até o tenant Qlik Cloud e até o Oracle fonte (item 2.3 do [Guia de Implementação](Guia_Implementacao_Novo_Tenant.md#23-conectividade-com-a-fonte-de-dados-oracle)).

### A.3 Direct Access Gateway

Usado pelas conexões `da-*` (Data Analytics) em [data-connections/](data-connections/) — ex. `da-oracle` declara `Data gateway: QDAG_VendasODS`. É um gateway separado do Data Movement Gateway (item A.2, usado pela conexão `di-oracle` do CDC): o `di-oracle` alimenta o pipeline atual (Landing → Bronze → Silver → Gold); o `da-*` é a via de conexão direta/legada usada pelos scripts `ext001-3` (ver nota no [Guia de Implementação](Guia_Implementacao_Novo_Tenant.md)). Se o fluxo `ext00x` não for reativado, este gateway não precisa ser instalado — mas ele é parte da configuração documentada do projeto, não só uma possibilidade futura.

**Diferente de A.1 e A.2, este gateway não roda em Docker/Linux — exige uma máquina Windows Server dedicada.** Todo o procedimento abaixo é manual, feito na própria máquina Windows; não pode ser executado pelo Claude.

**Requisitos:**
- Windows Server 2016, 2019, 2022 ou 2025, dedicado (não instalar no próprio servidor do banco de dados, nem junto com outros produtos Qlik como Data Transfer/Sense Desktop/Sense Enterprise), atrás de firewall com acesso às fontes de dados
- Hardware: recomendado 8 cores / 32 GB RAM / 5 GB de disco; mínimo 4 cores / 8 GB RAM / 5 GB (só dev/teste)
- Pré-requisitos de software: .NET Framework 4.8, .NET 6.0.x Runtime + ASP.NET Core Runtime, .NET 8.0.x Runtime + ASP.NET Core Runtime (últimos patches), Microsoft Visual C++ 2015-2022 Redistributable (x64)

**Passos:**
1. **Download**: Management Console → Administration → Data Gateways → Deploy → baixar `qlik-data-gateway-direct-access.exe`
2. **Instalar**: copiar o executável para o Windows Server e rodar (interativo, ou silencioso com `AcceptEula=yes`)
3. **Configurar**: definir a URL do tenant (e proxy, se necessário) via linha de comando; gerar a chave de registro com `connectoragent qcs generate_keys`
4. **Registrar**: Management Console → Data Gateways → Create → tipo **Direct Access** → associar a um Space → colar a chave de registro
5. **Iniciar o serviço**: via Windows Services ou linha de comando
6. **Validar**: status deve aparecer **Connected** na Management Console; só então criar as conexões de dados que usarão esse gateway

**Limitações conhecidas**: conecta a um único tenant por instalação; queries de script limitadas a 500.000 caracteres; se o servidor reiniciar durante um reload de app, o reload falha e precisa ser refeito.

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
