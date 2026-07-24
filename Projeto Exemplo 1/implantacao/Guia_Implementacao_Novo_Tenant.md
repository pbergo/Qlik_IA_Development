# Guia de Implementação — Projeto VendasODS em um Tenant Qlik Cloud Novo

> Este guia cobre **o que precisa existir/estar pronto antes de instalar o projeto** (licenciamento, papéis de usuário, infraestrutura, ambiente de deploy). Para o passo a passo de instalação em si (comandos, ordem de execução, validação), ver [Guia_Instalacao_Projeto.md](Guia_Instalacao_Projeto.md).
> Este projeto (Projeto Exemplo 1) ainda não foi implantado em nenhum tenant real — este guia é prospectivo, não um relato de deploy. Itens marcados "a validar" devem ser confirmados na primeira implementação real.

---

## 1. Arquitetura de referência

Diagrama de referência do padrão geral (não específico deste projeto, mas útil como contexto): [../projeto/architecture/Medallion Architecture.pdf](../projeto/architecture/Medallion%20Architecture.pdf) (fonte editável: [.drawio](<../projeto/architecture/Medallion Architecture.drawio>) / [.pptx](<../projeto/architecture/Medallion Architecture.pptx>)). O diagrama ilustra o padrão geral de arquitetura Qlik Cloud (camadas Landing → Bronze → Silver → Gold em S3, Qlik Data Product como ponto de controle de qualidade/exposição, IdP e separação PROD/DEV) — **inclui itens que não fazem parte do escopo real deste projeto específico**: o Data Movement Gateway (CDC) mostrado no diagrama não é usado aqui.

- **Camadas Bronze → Silver → Gold**, todas em Amazon S3.
- **Extração via SQL direto** (não CDC): os scripts `ext001_cadastros.qvs`, `ext002_pedidos_peditem.qvs` e `ext003_devolucoes.qvs` leem a fonte Oracle diretamente através da conexão de Data Analytics `da-oracle` (Direct Access Gateway) e gravam Parquet na camada Bronze. `ext001` faz carga completa (full) das tabelas de cadastro; `ext002`/`ext003` fazem carga incremental por janela de dias sobre `Data_Venda`/`Data_Devolucao`.
- **Task Orchestration** via Qlik Automation — a Automation `VendasODS_Pipeline_Execution` ([../projeto/automation/](../projeto/automation/)) executa em cascata os 9 apps do pipeline (extração → transformação → analytics).

Modelo dimensional: [../projeto/modelos-dados/modelo_dimensional_kimball.dot](../projeto/modelos-dados/modelo_dimensional_kimball.dot) (referência conceitual) / [modelo_dimensional_qlik.dot](../projeto/modelos-dados/modelo_dimensional_qlik.dot) (modelo efetivamente implementado no Qlik, com tabela-ponte `link_fato`). ERD da fonte: [../projeto/modelos-dados/VendasODS-ERD.jpg](../projeto/modelos-dados/VendasODS-ERD.jpg).

**Nota sobre o Data Movement Gateway / CDC**: este projeto não usa CDC. Se no futuro este projeto migrar para extração via CDC (como o Projeto Exemplo 2 deste repositório), a extração `ext00x` seria substituída por um projeto de Data Integration + Data Movement Gateway; isso está fora do escopo atual.

---

## 2. Pré-requisitos

### 2.1 Tenant Qlik Cloud

**Tipo de tenant**: um tenant **Qlik Cloud Analytics** (SKU do tipo "Qlik Data Analytics" / `qda`), **sem** o módulo de Data Integration (`qcdi`). Isso é diferente do tenant usado pelo Projeto Exemplo 2, que roda em um plano com os dois módulos combinados (`plan-classic-qda-qcdi-premium`, confirmado via `qlik-cli` num deploy real) — aqui só a parte `qda` é necessária, já que este projeto não usa CDC/Data Integration.

> ⚠️ Este nome de SKU é inferido por analogia ao plano do Projeto Exemplo 2 (removendo a parte `qcdi`), não confirmado via inspeção de um tenant real deste projeto (que nunca foi implantado — ver nota no topo deste guia). Confirmar o nome exato do plano com o time comercial/CS da Qlik ou via `qlik-cli`/Management Console assim que houver um tenant de destino.

O tenant de destino precisa ter os seguintes toggles/capacidades habilitados:

| Entitlement | Por quê é necessário |
|---|---|
| `relationalRDMSConnectivity` | Permite conectar a um banco relacional (Oracle) como fonte via Data Analytics |
| `dataAnalyticsCapacity` | Volume de dados analisados pelos apps (ext00x, trf00x, viz001) |
| `Application Automation` com cota de execuções/mês e concorrência suficientes | Roda a Automation `VendasODS_Pipeline_Execution` (a cada 15 min, 9 etapas) |
| Ao menos 1 seat **Full User** disponível | Analyzer/Basic não cria apps nem automations |

Este projeto **não** exige `dataIntegrationServices`, `cdcBulkDataMovement` nem `dataDelivery` (módulos de Data Integration) — esses só seriam necessários se o projeto migrasse para extração via CDC. Não exige `dataProduct`/`dataQuality`/`discoveryAgent`/`lineageConnectorQlikIncluded` para o pipeline funcionar; esses entitlements de catálogo/qualidade (usados pelo Projeto Exemplo 2 nos checkpoints de Qlik Data Product) são opcionais aqui, só necessários se o projeto adotar Data Products/glossário.

### 2.2 Tipo de usuário necessário para a implementação
Quem for configurar o tenant precisa, ao menos durante a fase de implementação, dos papéis:

- `Data Admin` / `Data Services Contributor` — criar as conexões de dados
- `Data Space Creator` + `Shared Space Creator` — criar os espaços do projeto
- `Automation Creator` — criar/importar a Automation
- `Analytics Admin` — gerenciar apps

Depois do setup inicial, o dia a dia do projeto pode operar com papel mais restrito (ex. `producer`/`codeveloper` só nos espaços do projeto).

### 2.3 Conectividade com a fonte de dados (Oracle)
- Host/porta acessíveis a partir de onde o Direct Access Gateway for instalado. Valores de referência usados nos arquivos deste projeto (ver aviso de "exemplo/snapshot" em [data-connections/di-oracle.md](data-connections/di-oracle.md) / [da-oracle.md](data-connections/da-oracle.md) — **confirmar/atualizar por tenant antes de usar**):
  - Servidor de referência: `192.168.1.27:1521`, service name `XEPDB1`
  - Schema: `vendasods` / `VENDASODS`
- Usuário de banco com permissão de leitura no schema (ver [base-dados/database_config_vendasods.sql](base-dados/database_config_vendasods.sql) para os grants necessários).
- Diferente de um setup CDC, **não é necessário** habilitar supplemental logging nem modo ARCHIVELOG na instância Oracle — esses só são exigidos por replicação baseada em redo log (Data Movement Gateway), que este projeto não usa.

### 2.4 Servidor/VM para o Direct Access Gateway
- **Windows Server dedicado** (2016/2019/2022/2025) — o Direct Access Gateway, diferente do Data Movement Gateway, não roda em Docker/Linux. Não instalar no mesmo servidor do banco de dados nem junto com outros produtos Qlik.
- Rede de saída até o tenant Qlik Cloud de destino e rede de entrada até o Oracle fonte (item 2.3).
- Hardware recomendado: 8 cores / 32 GB RAM / 5 GB de disco (mínimo 4 cores / 8 GB RAM para dev/teste).
- Este é o único item de infraestrutura que **precisa ser feito manualmente** — não pode ser automatizado pelo Claude (exige rodar um instalador interativo em uma máquina Windows específica).

### 2.5 Conta/bucket AWS S3
- Bucket dedicado, região definida.
- Par de chaves de acesso (Access Key/Secret Key) com permissão de leitura/escrita nos prefixos `bronze/`, `silver/`, `gold/` (ver [README.md](../README.md) para a convenção de pastas).

### 2.6 Ambiente de deploy via Claude
A máquina/ambiente onde o Claude roda precisa ter:
- Os arquivos do projeto disponíveis localmente (via `git clone` do repositório ou download ZIP).
- `qlik-cli` instalado, com um **contexto novo** apontando para o tenant de destino (`qlik context create`), autenticado com a API key desse tenant.
- Usuário/API key com os papéis listados em 2.2, já que o Claude executa as criações via API em nome desse usuário.
- Licença Claude recomendada: Pro (ou superior) — o deploy é um processo longo (muitas chamadas de ferramenta em sequência).

### 2.7 Integração MCP configurada
Divisão de responsabilidade:

| Camada | Ferramenta | Cobre |
|---|---|---|
| Admin/lifecycle | `qlik-cli` (REST API) | Spaces, conexões de dados, apps (criar + carregar script + reload), automations, gateways, licenças, usuários |
| Conteúdo analítico/catálogo | Servidor MCP Qlik | Sheets/gráficos dentro dos apps (relevante para `viz001`), dimensões/medidas mestres, data products, glossário |

O Claude precisa de um **servidor MCP Qlik registrado** apontando para a API do tenant de destino. Passos (caminho comum via conta claude.ai, a validar se aplicável ao seu ambiente):

1. Gerar credenciais no Qlik Cloud: criar/identificar um usuário/service account com os papéis de 2.2 e gerar um cliente OAuth ([qlik.dev/authenticate/oauth/create/create-oauth-client](https://qlik.dev/authenticate/oauth/create/create-oauth-client/)).
2. Registrar o conector MCP na conta claude.ai: Configurações → Personalizar → Conectores → Adicionar → Adicionar conector personalizado, com URL remota `https://<tenant>.<região>.qlikcloud.com/api/ai/mcp` e o OAuth Client ID gerado no passo 1.
3. Instalar a extensão *Claude Code for VS Code* (se for esse o ambiente), logar e autorizar.
4. Validar com um prompt simples, ex. *"Conecte-se ao Qlik Cloud e liste os espaços disponíveis."*

Boas práticas: manter segredos/tokens fora do repositório, revisar periodicamente as permissões do usuário/service account.

### 2.8 Mesmo usuário em todos os pontos de acesso

**A API key do contexto `qlik-cli` (2.6) e a API key do servidor MCP (2.7) precisam pertencer ao mesmo usuário do tenant** — e esse usuário precisa ter os papéis listados em 2.2. Objetos criados via API ficam associados ao usuário dono da API key que os criou; misturar usuários entre `qlik-cli` e MCP causa falhas de permissão em passos posteriores (reload de app, edição de conteúdo do `viz001`, autorização OAuth da Automation).

---

## 3. Ferramentas a baixar/instalar

| Ferramenta | Uso | Observação |
|---|---|---|
| **Git** *(opcional)* | Clonar o repositório | Só necessário se optar por `git clone` em vez de baixar o ZIP |
| **qlik-cli** | Automação de tenant admin (spaces, conexões, apps, automations) | Baixar em [github.com/qlik-oss/qlik-cli/releases](https://github.com/qlik-oss/qlik-cli/releases), extrair `qlik.exe` para uma pasta no PATH e validar com `qlik --version` |
| **VS Code** + extensão *Claude Code for VS Code* | IDE de desenvolvimento com Claude integrado (ver 2.7) | — |
| **Instalador do Qlik Data Analytics Direct Access Gateway** | Habilita a conexão `da-oracle` | Baixado a partir do tenant Qlik Cloud de destino (Management Console → Data Gateways → Deploy); exige Windows Server dedicado, ver 2.4 |
| Driver/cliente Oracle (a confirmar) | Pode ser exigido pelo conector Oracle do gateway | Validar na documentação do conector no momento da instalação |
| (Opcional) Cliente SQL Oracle (SQL Developer, etc.) | Validar conectividade com a fonte antes de configurar o gateway | Não obrigatório, útil para diagnóstico |
| (Opcional) `gvenzl/oracle-xe` via Docker | Subir uma instância Oracle local de teste, se não houver uma disponível | Ver [Guia_Instalacao_Projeto.md, Apêndice A](Guia_Instalacao_Projeto.md#apêndice-a-infraestrutura-via-docker-opcional) |

---

## 4. Segredos e credenciais a preparar (checklist)

**Convenção do repositório**: sempre que o Claude precisar de uma chave de API ou senha de conexão (nesta implantação ou em qualquer outra, deste ou de outro projeto do repositório), ela deve ser **solicitada ao usuário** e registrada em um arquivo `secrets.env` na **raiz do repositório** (um nível acima de `Projeto Exemplo 1/` e `Projeto Exemplo 2/` — não dentro de `implantacao/secrets/`). Esse arquivo já é coberto pelo `.gitignore` (`*.env`, regra na raiz) — nunca é versionado, então pode conter valores reais com segurança. Isso evita pedir o mesmo valor mais de uma vez ao longo do deploy. Ver [Guia_Instalacao_Projeto.md §0](Guia_Instalacao_Projeto.md#0-coletar-credenciais-e-registrar-em-secretsenv) para o passo correspondente.

Valores a solicitar e registrar **antes** de iniciar o deploy:

- [ ] **API key do tenant Qlik Cloud de destino** — precisa ser gerada pelo **mesmo usuário autenticado no Claude Code/MCP** (ver 2.7/2.8), e essa mesma chave é reaproveitada para configurar o contexto do `qlik-cli` (`qlik context create ... --api-key <api-key>`). Não usar API keys de usuários diferentes entre `qlik-cli` e MCP — ver 2.8.
- [ ] Usuário/senha de conexão com o Oracle fonte (schema `vendasods`/`VENDASODS`)
- [ ] Access Key / Secret Key do bucket S3
- [ ] Nome do bucket S3 e região
- [ ] Nome/host de referência do Direct Access Gateway a ser registrado

Tratar o conteúdo do arquivo como sensível localmente (não colar em chat/log fora da própria sessão de deploy).

---

## 5. Papéis nos espaços (pós-implementação)

Atribuir papéis (`producer`/`codeveloper`/`consumer`) aos usuários finais nos espaços, uma vez que o setup inicial (feito com papéis de admin, item 2.2) estiver concluído.

---

## 6. Riscos e observações

- **`di-oracle.md`/`di-s3.md` não são usados pelo pipeline atual**: este projeto extrai via `da-oracle` (SQL direto), não via CDC. Os arquivos `di-oracle.md`/`di-s3.md` em [data-connections/](data-connections/) existem por convenção do template (todo projeto documenta as 4 conexões possíveis), mas não são consumidos por nenhum script hoje — reservados para uma futura migração a CDC.
- **`da-oracle.md`/`di-oracle.md` são compartilhados entre deploys/tenants**: o `Server`/`Host name` neles é um exemplo/snapshot, não uma constante do projeto — confirmar o valor real do tenant de destino antes de criar a conexão (ver aviso nos próprios arquivos).
- **Segredos em texto plano**: se o `secrets.env` na raiz do repositório ou o JSON da Automation vierem a conter credenciais reais, nunca commitá-los — ver 4 e a nota sobre `executionToken` em [../projeto/automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md](../projeto/automation/VendasODS_Pipeline_Execution_Requisitos_Tecnicos.md).
- **Sem notificação de falha real** na Automation: os blocos `Output`/`Error` só exibem status e interrompem a execução — não há conector de e-mail/Slack/Teams alertando um responsável. Considerar adicionar se monitoramento ativo for necessário.
- **`dim_tempo` de `trf005_gold_star_schema.qvs` é uma dimensão conformada** (mistura Data_Venda + Data_Remessa + Data_Devolucao no mesmo calendário) — ao analisar `gen_data`/`key_data`, sempre olhar o fato associado (`fact_vendas`/`fact_remessas`/`fact_devolucoes`) para saber a que a data se refere, nunca `dim_tempo` isolada.
- **Itens a validar na primeira implementação real** (este projeto ainda não foi implantado): tempo real de execução da cascata de 9 etapas frente à frequência do schedule (15 min); se o Direct Access Gateway exige algum driver/cliente Oracle adicional no host Windows; se a janela de incremental de `vWindowDays = 14` (ext002/ext003) é adequada ao volume real de dados do tenant de destino.
