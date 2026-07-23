# Guia de Implementação — Projeto VendasODS em um Tenant Qlik Cloud Novo

> Este guia cobre **o que precisa existir/estar pronto antes de instalar o projeto** (licenciamento, papéis de usuário, infraestrutura, ambiente de deploy). Para o passo a passo de instalação em si (comandos, ordem de execução, validação), ver [Guia_Instalacao_Projeto.md](Guia_Instalacao_Projeto.md).
> Repositório: [https://github.com/pedrobergo/Qlik_IADataEngineering.git](https://github.com/pedrobergo/Qlik_IADataEngineering.git) (público)
> Levantado por análise do repositório + inspeção do tenant atual via `qlik-cli` em 2026-07-23.

> ⚠️ **Achado de segurança a resolver antes de qualquer coisa**: ver seção 6.

---

## 1. Arquitetura de referência

Diagrama de referência do padrão geral (não específico deste projeto, mas útil como contexto): [architecture/Medallion Architecture.pdf](architecture/Medallion%20Architecture.pdf) (fonte editável: [architecture/Medallion Architecture.drawio](architecture/Medallion%20Architecture.drawio) / [.pptx](architecture/Medallion%20Architecture.pptx)). Ele ilustra o padrão geral de arquitetura Qlik Cloud (camadas Landing → Bronze → Silver → Gold em S3, Data Movement Gateway para CDC, Qlik Data Product como ponto de controle de qualidade/exposição, IdP e separação PROD/DEV) — inclui itens (Identity Provider, ambientes PROD/DEV separados) que são apenas referência geral do padrão e **não fazem parte do escopo de implementação deste projeto específico**.

- **Camadas Landing → Bronze → Silver → Gold**, todas em Amazon S3, com o **Qlik Data Product** usado em dois pontos de controle: logo após o Bronze (qualidade/padronização) e após o Gold (exposição para consumo).
- **Data Movement Gateway** fazendo CDC da fonte Oracle até a área de Landing — é o item que este projeto de fato usa.
- **Task Orchestration** via Qlik Automate — é a peça que este projeto implementa como a Automation `VendasODS_Pipeline_Execution`.

Modelo dimensional: [Modelos_Dados/modelo_dimensional_kimball.dot](Modelos_Dados/modelo_dimensional_kimball.dot) / [modelo_dimensional_qlik.dot](Modelos_Dados/modelo_dimensional_qlik.dot). ERD da fonte: [Modelos_Dados/VendasODS-ERD.jpg](Modelos_Dados/VendasODS-ERD.jpg). Projeto de Data Integration (CDC) exportado: [data-integration/P01_VendasODS_S3/](data-integration/P01_VendasODS_S3/).

**Nota sobre a abordagem antiga**: os scripts `ext001_cadastros.qvs`, `ext002_pedidos_peditem.qvs` e `ext003_devolucoes.qvs` representam uma abordagem anterior (extração direta via SQL, conector `da-mysql`, Direct Access Gateway) que **foi substituída** por `str001` lendo da camada Landing via CDC. Este projeto usa apenas a arquitetura atual (CDC/Oracle). Os scripts `ext00x` permanecem no repositório como histórico.

---

## 2. Pré-requisitos

### 2.1 Tenant Qlik Cloud
O tenant de destino precisa ter um plano/entitlements equivalente ao do tenant atual (`plan-classic-qda-qcdi-premium`), com os seguintes toggles/capacidades habilitados:

| Entitlement | Por quê é necessário |
|---|---|
| `dataIntegrationServices` | Habilita o módulo Qlik Data Integration (projeto/tarefas) |
| `cdcBulkDataMovement` | Habilita replicação CDC (usada por `str001`) |
| `dataDelivery` | Permite Data Movement para S3 como destino |
| `relationalRDMSConnectivity` | Permite conectar a um banco relacional (Oracle) como fonte |
| `dataProduct` / `dataQuality` / `discoveryAgent` / `lineageConnectorQlikIncluded` | Suportam os checkpoints de Qlik Data Product mostrados no diagrama (seção 1) |
| `Application Automation` com cota de execuções/mês e concorrência suficientes | Roda a Automation `VendasODS_Pipeline_Execution` (a cada 15 min) |
| Ao menos 1 seat **Full User** disponível | Analyzer/Basic não cria apps, automations nem projetos DI |

Capacidades de consumo a verificar (não bloqueantes, mas monitorar): `dataAnalyticsCapacity` (volume de dados analisados) e `dataServicesCapacity` (volume movido pelo DI por mês).

### 2.2 Tipo de usuário necessário para a implementação
Quem for configurar o tenant precisa, ao menos durante a fase de implementação, dos papéis:

- `Tenant Admin` — registrar o Data Movement Gateway, configurações de tenant
- `Data Admin` / `Data Services Contributor` — criar projeto de Data Integration e conexões de dados
- `Data Space Creator` + `Shared Space Creator` — criar os espaços do projeto
- `Automation Creator` — criar/importar a Automation
- `Analytics Admin` — gerenciar apps

Depois do setup inicial, o dia a dia do projeto pode operar com papel mais restrito (ex. `producer`/`codeveloper` só nos espaços do projeto); o admin amplo acima é necessário apenas durante a implementação.

### 2.3 Conectividade com a fonte de dados (Oracle)
- Host/porta acessíveis a partir de onde o Data Movement Gateway for instalado. Valores documentados no tenant atual (validar se aplicam ao ambiente novo ou se há uma instância Oracle diferente):
  - Servidor: `192.168.1.27:1521` (SID/service documentado de forma inconsistente entre `di-oracle.md` = `XEPDB1` e `da-oracle.md` = `Oracle` — **confirmar o service name correto antes de configurar a conexão**)
  - Schema: `vendasods` / `VENDASODS`
- Usuário de banco com permissão de leitura (e leitura de redo log / privilégios necessários para CDC, conforme requisito do conector Oracle do Qlik Data Integration).

### 2.4 Servidor/VM para o Data Movement Gateway
- Host (Windows ou Linux, conforme suportado pelo Qlik Data Movement Gateway) com:
  - Rede de saída até o tenant Qlik Cloud de destino
  - Rede de entrada até o Oracle fonte (item 2.3)
- Este é o único item de infraestrutura que **precisa ser feito manualmente** — não pode ser automatizado pelo Claude (exige rodar um instalador em uma máquina física/VM específica).

### 2.5 Conta/bucket AWS S3
- Bucket dedicado (novo, não reaproveitar o bucket do tenant atual)
- Região definida (atualmente `us-west-2`)
- Par de chaves de acesso (Access Key/Secret Key) com permissão de leitura/escrita nos prefixos `materlake/landing/`, `materlake/bronze/`, `materlake/silver/`, `materlake/gold/`

### 2.6 Ambiente de deploy via Claude
A máquina/ambiente onde o Claude roda precisa ter:
- **Git instalado e no PATH** (⚠️ não está presente no ambiente usado para este levantamento — precisa ser instalado antes do deploy)
- Acesso para `git clone https://github.com/pedrobergo/Qlik_IADataEngineering.git` (repositório público, não exige token/SSH key)
- `qlik-cli` instalado, com um **contexto novo** apontando para o tenant de destino (`qlik context create`), autenticado com a API key desse tenant
- Usuário/API key com os papéis listados em 2.2, já que o Claude executa as criações via API em nome desse usuário

### 2.7 Integração MCP configurada
Nem tudo é feito via `qlik-cli`/REST admin API. Divisão de responsabilidade:

| Camada | Ferramenta | Cobre |
|---|---|---|
| Admin/lifecycle | `qlik-cli` (REST API) | Spaces, conexões de dados, apps (criar + carregar script + reload), projetos de Data Integration, automations, gateways, licenças, usuários |
| Conteúdo analítico/catálogo | Servidor MCP Qlik (ex.: o `pbergo-qcda` usado nesta sessão) | Sheets/gráficos dentro dos apps (relevante para `viz001`), dimensões/medidas mestres, data products, glossário, qualidade de dataset, lineage |

O Claude precisa de um **servidor MCP Qlik registrado** (ex. via `claude mcp add`) apontando para a API do tenant de destino, autenticado com a API key desse tenant novo. Sem isso, a parte de conteúdo analítico/catálogo não pode ser feita.

---

## 3. Ferramentas a baixar/instalar

| Ferramenta | Uso | Observação |
|---|---|---|
| **Git** | Clonar o repositório | Ausente no ambiente testado — instalar antes de tudo |
| **qlik-cli** | Automação de tenant admin (spaces, conexões, apps, di-projects, automations) | Já usado neste levantamento (`C:\Program Files\Qlik\Qlik-cli\qlik.exe`) |
| **Instalador do Qlik Data Movement Gateway** | Habilita a replicação CDC Oracle → S3 | Baixado a partir do tenant Qlik Cloud de destino (Management Console → Data Gateways) |
| Driver/cliente Oracle (a confirmar) | Pode ser exigido pelo conector Oracle do gateway | Validar na documentação do conector no momento da instalação |
| (Opcional) Cliente SQL Oracle (SQL Developer, etc.) | Validar conectividade com a fonte antes de configurar o gateway | Não obrigatório, útil para diagnóstico |

---

## 4. Segredos e credenciais a preparar (checklist)

Ter em mãos **antes** de iniciar o deploy (sem reutilizar os valores do tenant atual):

- [ ] API key do tenant Qlik Cloud de destino (para o contexto `qlik-cli` e para o servidor MCP)
- [ ] Usuário/senha do Oracle fonte (schema `vendasods`/`VENDASODS`)
- [ ] Access Key / Secret Key do novo bucket S3
- [ ] Nome do novo bucket S3 e região
- [ ] Nome/host de referência do Data Movement Gateway a ser registrado

> Não reaproveitar nem versionar os valores reais desse checklist em texto plano no repositório — ver seção 6.

---

## 5. Papéis nos espaços (pós-implementação)

Atribuir papéis (`producer`/`codeveloper`/`consumer`) aos usuários finais nos espaços, uma vez que o setup inicial (feito com papéis de admin, item 2.2) estiver concluído.

---

## 6. Riscos e observações (achados durante o levantamento)

- **Segredos em texto plano no repositório**: [secrets/secrets.env](secrets/secrets.env) contém API keys, credenciais de banco e chaves AWS reais; o JSON da Automation contém um `executionToken`. Recomenda-se rotacionar essas credenciais e remover os valores reais do histórico do git — o repositório já é público hoje.
- **Sem notificação de falha real** na Automation: os blocos `Output`/`Error` só exibem status e interrompem a execução — não há conector de e-mail/Slack/Teams alertando um responsável. Considerar adicionar se monitoramento ativo for necessário.
- **Inconsistência no service name Oracle** entre `data-connections/di-oracle.md` (`XEPDB1`) e `data-connections/da-oracle.md` (`Oracle`) — confirmar o valor correto com o DBA da fonte antes de configurar a conexão no tenant novo.
- **Scripts `ext001-3` são legado**: não fazem parte do deploy atual (substituídos por `str001` via CDC), mas permanecem no repositório — evitar reativá-los por engano.
- **Limitações do conector S3 V2** (sem suporte a wildcard) documentadas nos comentários de `str001_bronze_vendasods.qvs` — validar se persistem no tenant/conector novo antes de assumir que o workaround (listagem completa + filtro client-side) ainda é necessário.
