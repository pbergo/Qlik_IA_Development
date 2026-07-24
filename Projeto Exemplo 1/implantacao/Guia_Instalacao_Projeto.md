# Guia de Instalação — Projeto VendasODS (Projeto Exemplo 1)

> Este guia assume que os pré-requisitos já foram atendidos — ver [Guia_Implementacao_Novo_Tenant.md](Guia_Implementacao_Novo_Tenant.md) antes de seguir os passos abaixo (licenciamento do tenant, papéis de usuário, gateway, bucket S3, ambiente com `qlik-cli`/MCP configurados e os arquivos do projeto disponíveis localmente).
> Este projeto usa extração via SQL direto (`ext001`/`ext002`/`ext003`, conexão `da-oracle`, Direct Access Gateway) — **não** CDC/Data Movement Gateway. Se você está procurando o fluxo baseado em CDC, veja o Projeto Exemplo 2 deste repositório.

---

## Visão geral da sequência

0. Coletar credenciais e registrar em `secrets.env` (raiz do repositório)
1. Preparar o ambiente local (`qlik-cli`, MCP)
2. Preparar a fonte Oracle (usuário, tabelas e dados de exemplo)
3. *(manual)* Instalar e registrar o Direct Access Gateway
4. Criar os Spaces
5. Criar as conexões de dados
6. Criar os apps e carregar os scripts (9 apps: extração → transformação → analytics)
7. Construir o conteúdo analítico do `viz001` (via MCP)
8. Importar e ajustar a Automation
9. Validar

---

## 0. Coletar credenciais e registrar em `secrets.env`

Antes de qualquer outra etapa, o Claude deve **solicitar ao usuário** e registrar as credenciais abaixo em um arquivo `secrets.env` na **raiz do repositório** (`../../secrets.env` a partir desta pasta — um nível acima de `Projeto Exemplo 1/`, não dentro de `implantacao/secrets/`). Esse arquivo é coberto pela regra `*.env` do `.gitignore` na raiz, então nunca é versionado — pode conter valores reais com segurança.

Esta é uma convenção do repositório como um todo: **toda vez que uma etapa deste guia (ou qualquer interação futura) exigir uma chave de API ou senha de conexão ainda não registrada, ela deve ser pedida ao usuário e gravada nesse mesmo `secrets.env`**, para não ser solicitada de novo.

Credenciais a coletar nesta etapa:

- **API key do tenant Qlik Cloud de destino** — precisa ser gerada pelo **mesmo usuário autenticado no Claude Code/MCP** (ver §2.7/§2.8 do [Guia de Implementação](Guia_Implementacao_Novo_Tenant.md)), já que essa mesma chave será reaproveitada para configurar o contexto do `qlik-cli` no passo 1 abaixo.
- **Senha de conexão com o Oracle fonte** (usuário `vendasods`, schema `VENDASODS`) — usada na conexão `da-oracle` (passo 5).
- **Access Key e Secret Key do bucket S3** de destino — usadas na conexão `da-s3` (passo 5).

Ver [Guia_Implementacao_Novo_Tenant.md §4](Guia_Implementacao_Novo_Tenant.md#4-segredos-e-credenciais-a-preparar-checklist) para o checklist completo (inclui também nome do bucket/região e nome de referência do gateway).

## 1. Preparar o ambiente local

Obter os arquivos do projeto por uma das duas formas:

- **Git**: `git clone <URL-do-repositório>`
- **Download ZIP**: baixar o ZIP do repositório e extrair localmente

```
qlik context create <nome-do-contexto> --server https://<tenant-novo>.qlikcloud.com --api-key <api-key>
qlik context use <nome-do-contexto>
```

Usar aqui a mesma API key registrada no passo 0.

Registrar o servidor MCP Qlik apontando para o mesmo tenant — ver [Guia_Implementacao_Novo_Tenant.md §2.7](Guia_Implementacao_Novo_Tenant.md#27-integração-mcp-configurada).

## 2. Preparar a fonte Oracle (usuário, tabelas e dados de exemplo)

Antes de instalar o gateway e criar a conexão `da-oracle`, o schema `VENDASODS` precisa existir no Oracle fonte com a estrutura e (opcionalmente) os dados de exemplo deste projeto. Se ainda não há uma instância Oracle disponível, ver [Apêndice A.1](#a1-banco-de-dados-oracle-container-oracle-xe) para subir uma via Docker. Os scripts estão em [base-dados/](base-dados/) e devem rodar nesta ordem:

| Ordem | Script | O que faz | Executar como |
|---|---|---|---|
| 1 | [base-dados/database_config_vendasods.sql](base-dados/database_config_vendasods.sql) | Cria o usuário `vendasods` e concede os grants de sessão/DDL usados pelo script seguinte (`CREATE ANY TABLE`, `CREATE TRIGGER`, `CREATE SEQUENCE`, etc.) — **sem** grants de CDC/LogMiner, que este projeto não usa | Usuário com privilégio de `GRANT` (ex. `system`) |
| 2 | [base-dados/create_database_vendasods.sql](base-dados/create_database_vendasods.sql) | Cria as 13 tabelas, as 15 Foreign Keys, o auto increment (`SEQUENCE` + `TRIGGER`, equivalente ao `AUTO_INCREMENT` da origem MySQL legada) e as demais constraints (`UNIQUE`, `CHECK`) | `vendasods` |
| 3 | [base-dados/vendasods_oracle_data.sql](base-dados/vendasods_oracle_data.sql) | Popula as tabelas com uma cópia dos dados de exemplo (`INSERT INTO`, já na ordem que respeita as FKs) | `vendasods` |

> Nota: `ALTER TABLE ... MODIFY ... AS IDENTITY` não funciona para converter uma coluna já existente em identity nativo do Oracle (`ORA-30673`, mesmo em tabela vazia) — por isso o auto increment usa o padrão clássico `SEQUENCE` + `TRIGGER`. Ver comentários no próprio `create_database_vendasods.sql`.

> Diferente de um setup CDC, **não é necessário** habilitar supplemental logging nem modo ARCHIVELOG na instância Oracle — a extração aqui é por SQL direto (`SELECT`), não por leitura de redo log.

## 3. Instalar e registrar o Direct Access Gateway *(manual)*

O Direct Access Gateway habilita a conexão `da-oracle`, usada pelos scripts `ext001`/`ext002`/`ext003`.

**Diferente de um Data Movement Gateway, este gateway não roda em Docker/Linux — exige uma máquina Windows Server dedicada.** Todo o procedimento abaixo é manual; não pode ser executado pelo Claude.

**Requisitos:**
- Windows Server 2016, 2019, 2022 ou 2025, dedicado (não instalar no próprio servidor do banco de dados, nem junto com outros produtos Qlik), atrás de firewall com acesso à fonte de dados
- Hardware: recomendado 8 cores / 32 GB RAM / 5 GB de disco; mínimo 4 cores / 8 GB RAM / 5 GB (só dev/teste)
- Pré-requisitos de software: .NET Framework 4.8, .NET 6.0.x Runtime + ASP.NET Core Runtime, .NET 8.0.x Runtime + ASP.NET Core Runtime (últimos patches), Microsoft Visual C++ 2015-2022 Redistributable (x64)

**Passos:**
1. **Download**: Management Console → Administration → Data Gateways → Deploy → baixar `qlik-data-gateway-direct-access.exe`
2. **Instalar**: copiar o executável para o Windows Server e rodar (interativo, ou silencioso com `AcceptEula=yes`)
3. **Configurar**: definir a URL do tenant (e proxy, se necessário) via linha de comando; gerar a chave de registro com `connectoragent qcs generate_keys`
4. **Registrar**: Management Console → Data Gateways → Create → tipo **Direct Access** → associar ao Space `VendasODS_Shared` (criado no passo 4) → colar a chave de registro
5. **Iniciar o serviço**: via Windows Services ou linha de comando
6. **Validar**: status deve aparecer **Connected** na Management Console; só então criar as conexões de dados que usarão esse gateway (passo 5 abaixo)

**Limitações conhecidas**: conecta a um único tenant por instalação; queries de script limitadas a 500.000 caracteres; se o servidor reiniciar durante um reload de app, o reload falha e precisa ser refeito.

## 4. Criar os Spaces

- **Shared space**: `VendasODS_Shared` (apps, conexões `da-*`, Automation)
- **Data space**: `VendasODS_Data` *(opcional para este projeto — só necessário se as conexões `di-*` reservadas forem criadas, ver nota no passo 5)*

## 5. Criar as conexões de dados

| Nome | Tipo | Space | Detalhe | Criação |
|---|---|---|---|---|
| `da-oracle` | Fonte (Data Analytics) | `VendasODS_Shared` | Host `<host>:1521/<service>`, schema `VENDASODS`, via Direct Access Gateway (passo 3) | **Manual (UI)** |
| `da-s3` | Storage (Analytics) | `VendasODS_Shared` | `File_AmazonS3ConnectorV2`, bucket novo, usado pelos apps para ler/gravar parquet | `qlik-cli`/API |

> **`da-oracle` é manual**: precisa ser criada pelo usuário via UI — Management Console/Hub → **Data Analytics → Connections**. Não pode ser feita pelo Claude via `qlik-cli`/API.

> **Conexões `di-oracle`/`di-s3` são opcionais**: existem em [data-connections/](data-connections/) por convenção do template, mas não são usadas por nenhum script deste projeto (que não faz CDC). Só crie essas conexões (e o Data Space `VendasODS_Data`) se planejar uma futura migração a CDC.

## 6. Criar os apps e carregar os scripts

Criar os 9 apps no space `VendasODS_Shared` e carregar os scripts, na ordem abaixo (respeita a dependência Extração → Silver → Gold → Analytics), rodando reload inicial de cada um antes de seguir para o próximo:

| Ordem | App | Script fonte |
|---|---|---|
| 1 | ext001_cadastros | [../projeto/scripts/ext001_cadastros.qvs](../projeto/scripts/ext001_cadastros.qvs) |
| 2 | ext002_pedidos_peditem | [../projeto/scripts/ext002_pedidos_peditem.qvs](../projeto/scripts/ext002_pedidos_peditem.qvs) |
| 3 | ext003_devolucoes | [../projeto/scripts/ext003_devolucoes.qvs](../projeto/scripts/ext003_devolucoes.qvs) |
| 4 | trf001_silver_vendasods | [../projeto/scripts/trf001_silver_vendasods.qvs](../projeto/scripts/trf001_silver_vendasods.qvs) |
| 5 | trf002_silver_devolucoes | [../projeto/scripts/trf002_silver_devolucoes.qvs](../projeto/scripts/trf002_silver_devolucoes.qvs) |
| 6 | trf003_silver_vendas | [../projeto/scripts/trf003_silver_vendas.qvs](../projeto/scripts/trf003_silver_vendas.qvs) |
| 7 | trf004_silver_devolucoes_consolidado | [../projeto/scripts/trf004_silver_devolucoes_consolidado.qvs](../projeto/scripts/trf004_silver_devolucoes_consolidado.qvs) |
| 8 | trf005_gold_star_schema | [../projeto/scripts/trf005_gold_star_schema.qvs](../projeto/scripts/trf005_gold_star_schema.qvs) |
| 9 | viz001_vendasods_analytics | [../projeto/scripts/viz001_vendasods_analytics.qvs](../projeto/scripts/viz001_vendasods_analytics.qvs) |

## 7. Conteúdo analítico do `viz001` (via MCP)

Construir sheets, gráficos e master items (dimensões/medidas) usando as ferramentas MCP (`qlik_create_sheet`, `qlik_add_chart`, `qlik_create_dimension`, `qlik_create_measure`, etc.) — não coberto pelo `qlik-cli`. Se o projeto usar catálogo/data products/glossário, registrar aqui também.

## 8. Importar e ajustar a Automation

Importar/recriar a partir de [../projeto/automation/VendasODS_Pipeline_Execution.json](../projeto/automation/VendasODS_Pipeline_Execution.json), ajustando:
- Os 9 `<APP_ID_...>` (Do Reload) para os **App IDs reais** criados no passo 6
- O `spaceId` para o `VendasODS_Shared` real
- Gerar um novo `executionToken` (não reaproveitar nenhum valor de exemplo) e **nunca commitar esse valor**
- Autorizar a conexão OAuth do conector "Qlik Cloud Services" dentro do editor da Automation, com um usuário que tenha permissão de reload nos 9 apps
- Definir o schedule (`startAt`, `RRULE:FREQ=MINUTELY;INTERVAL=15` como ponto de partida, timezone `America/Sao_Paulo`) e `maxConcurrentRuns: 1` — ajustar a frequência se o tempo real de execução das 9 etapas não couber na janela
- Detalhes completos: [../projeto/automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md](../projeto/automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md)

## 9. Validação / smoke test

- [ ] Schema `VENDASODS` no Oracle fonte com as 13 tabelas, FKs e dados de exemplo (scripts do passo 2 rodaram sem erro)
- [ ] Conexão `da-oracle` no status **Connected** e consegue rodar uma query de teste
- [ ] Reload manual de `ext001`/`ext002`/`ext003` conclui sem erro e grava os arquivos Parquet correspondentes em `bronze/vendasods/`
- [ ] **Extração incremental de fato capturando mudanças recentes**: usar [../projeto/scripts/GenerateData.py](../projeto/scripts/GenerateData.py) (menu "2. Gera Vendas Recentes", "5. Gera Devoluções...") para gerar tráfego de teste na fonte Oracle e confirmar que uma nova execução de `ext002`/`ext003` reflete essa mudança nos arquivos por ano correspondentes
- [ ] Reload manual de `trf001`→`trf005` conclui em cascata sem erro
- [ ] `viz001` reload conclui e as visualizações exibem dados (incluindo Devoluções)
- [ ] Rodar a Automation manualmente uma vez (`qlik automation run create`) e conferir `status: finished` sem erro em nenhuma etapa
- [ ] Confirmar que o schedule da Automation dispara sozinho na frequência esperada, dentro do tempo de execução real observado

Depois de validado, atribuir papéis (`producer`/`codeveloper`/`consumer`) aos usuários finais nos espaços — ver [Guia_Implementacao_Novo_Tenant.md §5](Guia_Implementacao_Novo_Tenant.md#5-papéis-nos-espaços-pós-implementação).

---

## Apêndice A: Infraestrutura via Docker (opcional)

Passos opcionais para quem ainda não tem uma instância Oracle fonte pronta e quer subir uma localmente via container.

### A.1 Banco de dados Oracle (container `oracle-xe`)

Usado para o passo 2 ("Preparar a fonte Oracle") quando não há uma instância Oracle já disponível. Imagem recomendada: [`gvenzl/oracle-xe`](https://hub.docker.com/r/gvenzl/oracle-xe) (mantenedor de referência da comunidade Oracle, wrapper Apache-2.0 em cima do Oracle Database XE oficial — não exige login/`docker login`, diferente do registry oficial `container-registry.oracle.com/database/express`). O PDB padrão dessa imagem é **`XEPDB1`**, que já é o service name assumido em [data-connections/da-oracle.md](data-connections/da-oracle.md) e nos scripts de [base-dados/](base-dados/) — não precisa ajustar nada nos scripts do passo 2.

```
mkdir C:\qlikfolder\oracle-xe
docker run -d --name oracle-xe-vendasods -p 1521:1521 ^
  -e ORACLE_PASSWORD=<senha-do-SYS-SYSTEM> ^
  -v C:\qlikfolder\oracle-xe:/opt/oracle/oradata ^
  gvenzl/oracle-xe
```

- `-v` monta um volume local para persistir os data files entre restarts do container.
- Acompanhar o boot (a primeira inicialização demora alguns minutos, criando o PDB): `docker logs -f oracle-xe-vendasods` até aparecer `DATABASE IS READY TO USE!`.
- Testar a conexão: `sqlplus system/<senha>@//localhost:1521/XEPDB1`.
- Com o container pronto, seguir o passo 2 normalmente, na ordem da tabela: [database_config_vendasods.sql](base-dados/database_config_vendasods.sql) como `system` (senha = `ORACLE_PASSWORD` definida acima), depois [create_database_vendasods.sql](base-dados/create_database_vendasods.sql) + [vendasods_oracle_data.sql](base-dados/vendasods_oracle_data.sql) como `vendasods`.

> Nota de licenciamento: o Oracle Database XE em si é gratuito, mas sujeito aos termos de licença da Oracle (Oracle Free Use Terms), aceitos implicitamente ao usar a imagem. Não é uma licença comercial completa do Oracle Database — adequado para dev/homologação/demo, não para produção com SLA.

---

## Padrões de nomenclatura a seguir durante a instalação

Ver [README.md §Padrões de Desenvolvimento](../README.md#padrões-de-desenvolvimento).
