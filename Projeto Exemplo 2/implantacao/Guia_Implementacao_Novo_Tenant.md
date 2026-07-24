# Guia de Implementação — Projeto VendasODS em um Tenant Qlik Cloud Novo

> Este guia cobre **o que precisa existir/estar pronto antes de instalar o projeto** (licenciamento, papéis de usuário, infraestrutura, ambiente de deploy). Para o passo a passo de instalação em si (comandos, ordem de execução, validação), ver [Guia_Instalacao_Projeto.md](Guia_Instalacao_Projeto.md).
> Repositório: [https://github.com/pedrobergo/Qlik_IADataEngineering.git](https://github.com/pedrobergo/Qlik_IADataEngineering.git) (público)
> Levantado por análise do repositório + inspeção do tenant atual via `qlik-cli` em 2026-07-23.

> ⚠️ **Achado de segurança a resolver antes de qualquer coisa**: ver seção 6.

---

## 1. Arquitetura de referência

Diagrama de referência do padrão geral (não específico deste projeto, mas útil como contexto): [../projeto/architecture/Medallion Architecture.pdf](../projeto/architecture/Medallion%20Architecture.pdf) (fonte editável: [../projeto/architecture/Medallion Architecture.drawio](../projeto/architecture/Medallion%20Architecture.drawio) / [.pptx](../projeto/architecture/Medallion%20Architecture.pptx)). Ele ilustra o padrão geral de arquitetura Qlik Cloud (camadas Landing → Bronze → Silver → Gold em S3, Data Movement Gateway para CDC, Qlik Data Product como ponto de controle de qualidade/exposição, IdP e separação PROD/DEV) — inclui itens (Identity Provider, ambientes PROD/DEV separados) que são apenas referência geral do padrão e **não fazem parte do escopo de implementação deste projeto específico**.

- **Camadas Landing → Bronze → Silver → Gold**, todas em Amazon S3, com o **Qlik Data Product** usado em dois pontos de controle: logo após o Bronze (qualidade/padronização) e após o Gold (exposição para consumo).
- **Data Movement Gateway** fazendo CDC da fonte Oracle até a área de Landing — é o item que este projeto de fato usa.
- **Task Orchestration** via Qlik Automate — é a peça que este projeto implementa como a Automation `VendasODS_Pipeline_Execution`.

Modelo dimensional: [../projeto/modelos-dados/modelo_dimensional_kimball.dot](../projeto/modelos-dados/modelo_dimensional_kimball.dot) / [modelo_dimensional_qlik.dot](../projeto/modelos-dados/modelo_dimensional_qlik.dot). ERD da fonte: [../projeto/modelos-dados/VendasODS-ERD.jpg](../projeto/modelos-dados/VendasODS-ERD.jpg). Projeto de Data Integration (CDC) exportado: [../projeto/data-integration/P01_VendasODS_S3/](../projeto/data-integration/P01_VendasODS_S3/).

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
  - Servidor: `192.168.1.27:1521`, service name `XEPDB1` (confirmado via conexão direta ao Oracle fonte)
  - Schema: `vendasods` / `VENDASODS`
- Usuário de banco com permissão de leitura (e leitura de redo log / privilégios necessários para CDC, conforme requisito do conector Oracle do Qlik Data Integration).
- **Configuração de instância (fora do escopo dos scripts de `base-dados/`, que só cuidam de usuário/grants/tabelas/dados)**: supplemental logging mínimo habilitado (`ALTER DATABASE ADD SUPPLEMENTAL LOG DATA`) e banco em modo **ARCHIVELOG**. Sem o primeiro, a tarefa CDC falha ao iniciar com `[SOURCE_UNLOAD]E: Minimal database supplemental logging level is not enabled [1020418]` (achado em deploy real, ver seção 6). Comandos de checagem/ativação: [Guia_Instalacao_Projeto.md §2](Guia_Instalacao_Projeto.md#2-preparar-a-fonte-oracle-usuário-tabelas-e-dados-de-exemplo).

### 2.4 Servidor/VM para o Data Movement Gateway
- Host (Windows ou Linux, conforme suportado pelo Qlik Data Movement Gateway) com:
  - Rede de saída até o tenant Qlik Cloud de destino
  - Rede de entrada até o Oracle fonte (item 2.3)
- Este é o único item de infraestrutura que **precisa ser feito manualmente** — não pode ser automatizado pelo Claude (exige rodar um instalador em uma máquina física/VM específica).

### 2.5 Conta/bucket AWS S3
- Bucket dedicado (novo, não reaproveitar o bucket do tenant atual)
- Região definida (atualmente `us-west-2`)
- Par de chaves de acesso (Access Key/Secret Key) com permissão de leitura/escrita nos prefixos `datalake/landing/`, `datalake/bronze/`, `datalake/silver/`, `datalake/gold/`

### 2.6 Ambiente de deploy via Claude
A máquina/ambiente onde o Claude roda precisa ter:
- Os arquivos do projeto disponíveis localmente, obtidos por uma de duas formas (testado em sessões diferentes, ambas funcionam e o restante do deploy não depende de qual foi usada):
  - **Git**: `git clone https://github.com/pedrobergo/Qlik_IADataEngineering.git` (repositório público, não exige token/SSH key) — requer Git instalado e no PATH
  - **Download ZIP**: baixar o ZIP do repositório (GitHub → Code → Download ZIP) e extrair localmente — **não exige Git instalado**, útil quando o ambiente não tem Git disponível
  - **Git não é um pré-requisito do ambiente de deploy em si** — só entra em jogo no momento do `git clone` inicial. Se o repositório já está clonado/baixado no ambiente por qualquer meio (ex. sessão anterior, outra máquina, pendrive), não há necessidade nenhuma de instalar Git para rodar o restante do deploy.
- `qlik-cli` instalado, com um **contexto novo** apontando para o tenant de destino (`qlik context create`), autenticado com a API key desse tenant
- Usuário/API key com os papéis listados em 2.2, já que o Claude executa as criações via API em nome desse usuário
- **Licença Claude recomendada: Pro (ou superior)**. O deploy completo é um processo longo (muitas chamadas de ferramenta em sequência: `qlik-cli`, MCP, leitura/escrita de arquivos) — um plano Free tende a esbarrar em limite de uso no meio do processo.

### 2.7 Integração MCP configurada
Nem tudo é feito via `qlik-cli`/REST admin API. Divisão de responsabilidade:

| Camada | Ferramenta | Cobre |
|---|---|---|
| Admin/lifecycle | `qlik-cli` (REST API) | Spaces, conexões de dados, apps (criar + carregar script + reload), projetos de Data Integration, automations, gateways, licenças, usuários |
| Conteúdo analítico/catálogo | Servidor MCP Qlik (ex.: o `pbergo-qcda` usado nesta sessão) | Sheets/gráficos dentro dos apps (relevante para `viz001`), dimensões/medidas mestres, data products, glossário, qualidade de dataset, lineage |

O Claude precisa de um **servidor MCP Qlik registrado** apontando para a API do tenant de destino, autenticado com a API key desse tenant novo. Sem isso, a parte de conteúdo analítico/catálogo não pode ser feita. Passos:

1. **Gerar credenciais no Qlik Cloud**: no tenant de destino, criar/identificar um usuário/service account com os papéis de 2.2 e gerar um cliente OAuth ([qlik.dev/authenticate/oauth/create/create-oauth-client](https://qlik.dev/authenticate/oauth/create/create-oauth-client/)). Anotar URL do tenant, Client ID/secret e escopo.
2. **Registrar o conector MCP na conta claude.ai** (caminho confirmado em deploy real — via app Claude Desktop ou direto em claude.ai no navegador, é a mesma conta/configuração): **Configurações → Personalizar → Conectores → Adicionar → Adicionar conector personalizado**:
   - Nome do conector, ex. `QlikMCP`
   - URL remota: `https://<tenant>.<região>.qlikcloud.com/api/ai/mcp`
   - Em Configurações Avançadas, informar o **OAuth Client ID** gerado no passo 1 (demais campos em branco)
   - Salvar, clicar em **Conectar**, logar no tenant Qlik Cloud e **Aprovar**
   - **O usuário do tenant usado aqui precisa ser o mesmo usado no restante do deploy** (ver 2.8)
   - Se for usar o app Claude Desktop (opcional, além da extensão VS Code): baixar em [claude.com/download](https://claude.com/download). Requisitos: Windows 10 build 19041+ ou Windows 11; instalar com conta de administrador (necessário para recursos como o agente autônomo Claude Cowork).
3. **Extensão Claude Code no VS Code**: instalar a extensão *Claude Code for VS Code*, abrir o ícone do Claude na paleta lateral, escolher **Claude.ai Subscription** (assinatura Pro/Max, ver 2.6) ou **Anthropic Console** (uso via API), logar e autorizar. **Não** é feito via CLI (`claude mcp add`) neste caminho — o conector já vem da conta claude.ai (passo 2).
4. **Validar**: reiniciar o VS Code (achado em deploy real: **necessário** para o conector aparecer disponível — não basta registrar em claude.ai e continuar na mesma sessão do VS Code) e testar com um prompt simples, ex. *"Conecte-se ao Qlik Cloud e liste os espaços disponíveis."* — se as ferramentas MCP do Qlik responderem, a integração está funcional.

Boas práticas: manter segredos/tokens fora do repositório (variáveis de ambiente, não valores fixos), revisar periodicamente as permissões do usuário/service account, atualizar credenciais e servidor MCP periodicamente, e preferir modelos mais simples/rápidos no dia a dia, reservando os mais caros (maior consumo de tokens/créditos) para tarefas difíceis.

### 2.8 Mesmo usuário em todos os pontos de acesso

**A API key do contexto `qlik-cli` (2.6) e a API key do servidor MCP (2.7) precisam pertencer ao mesmo usuário do tenant** — e esse usuário precisa ter os papéis listados em 2.2. Não funciona misturar API keys de usuários diferentes entre `qlik-cli` e MCP, nem usar um usuário para criar os objetos (spaces, apps, conexões) e outro para o restante do trabalho (conteúdo analítico, automation).

**Por quê**: objetos criados via API (spaces, apps, conexões, projeto de Data Integration) ficam associados ao usuário dono da API key que os criou; se `qlik-cli` e MCP autenticam como usuários diferentes, o segundo não enxerga/não tem permissão sobre o que o primeiro criou, e passos como reload de app, edição de conteúdo do `viz001` ou autorização OAuth da Automation (que também precisa ser feita por um usuário com `reload` nos 7 apps) falham por permissão.

---

## 3. Ferramentas a baixar/instalar

| Ferramenta | Uso | Observação |
|---|---|---|
| **Git** *(opcional)* | Clonar o repositório | Só necessário se optar por `git clone` em vez de baixar o ZIP do repositório (ver 2.6) — download via ZIP dispensa Git |
| **qlik-cli** | Automação de tenant admin (spaces, conexões, apps, di-projects, automations) | Baixar o pacote `qlik-Windows-x86_64.zip` em [github.com/qlik-oss/qlik-cli/releases](https://github.com/qlik-oss/qlik-cli/releases), extrair `qlik.exe` para uma pasta no PATH e validar com `qlik --version`. Já usado neste levantamento (`C:\Program Files\Qlik\Qlik-cli\qlik.exe`) |
| **VS Code** + extensão *Claude Code for VS Code* | IDE de desenvolvimento com Claude integrado (ver 2.7) | Extensões úteis adicionais: *Markdown Preview Enhanced*, *Ctrl-Q QVD Viewer*, *Rainbow CSV* |
| **Instalador do Qlik Data Movement Gateway** | Habilita a replicação CDC Oracle → S3 | Baixado a partir do tenant Qlik Cloud de destino (Management Console → Data Gateways) |
| Driver/cliente Oracle (a confirmar) | Pode ser exigido pelo conector Oracle do gateway | Validar na documentação do conector no momento da instalação |
| (Opcional) Cliente SQL Oracle (SQL Developer, etc.) | Validar conectividade com a fonte antes de configurar o gateway | Não obrigatório, útil para diagnóstico |

---

## 4. Segredos e credenciais a preparar (checklist)

Ter em mãos **antes** de iniciar o deploy (sem reutilizar os valores do tenant atual):

- [ ] API key do tenant Qlik Cloud de destino — **mesmo usuário** para o contexto `qlik-cli` e para o servidor MCP (ver 2.8), com os papéis de 2.2
- [ ] Usuário/senha do Oracle fonte (schema `vendasods`/`VENDASODS`)
- [ ] Access Key / Secret Key do novo bucket S3
- [ ] Nome do novo bucket S3 e região
- [ ] Nome/host de referência do Data Movement Gateway a ser registrado

> Não reaproveitar nem versionar os valores reais desse checklist em texto plano no repositório — ver seção 6.

**Prática recomendada**: no início do deploy, o Claude pode pedir esses valores ao usuário (API key do tenant, usuário/senha do Oracle, Access Key/Secret Key do S3, etc.) e registrá-los em [secrets/secrets.env](secrets/secrets.env), dentro do diretório do projeto — mesmo arquivo/formato já usado neste projeto (ver estrutura em [README.md](../README.md)). Isso evita repetir a mesma pergunta várias vezes ao longo do deploy.
- Se o ambiente usa Git, esse caminho já é coberto pelo `.gitignore` (`implantacao/secrets/*`, além de `*.env`) — o arquivo não é versionado nem enviado a um remote.
- Se os arquivos foram obtidos via download ZIP (sem Git — ver 2.6), não existe repositório/remote nesse ambiente, então também não há risco de compartilhamento por esse caminho.
- Em ambos os casos, tratar o conteúdo do arquivo como sensível localmente (não colar em chat/log fora da própria sessão de deploy).

---

## 5. Papéis nos espaços (pós-implementação)

Atribuir papéis (`producer`/`codeveloper`/`consumer`) aos usuários finais nos espaços, uma vez que o setup inicial (feito com papéis de admin, item 2.2) estiver concluído.

---

## 6. Riscos e observações (achados durante o levantamento)

- **Segredos em texto plano no repositório**: [secrets/secrets.env](secrets/secrets.env) contém API keys, credenciais de banco e chaves AWS reais; o JSON da Automation contém um `executionToken`. Recomenda-se rotacionar essas credenciais e remover os valores reais do histórico do git — o repositório já é público hoje.
- **Sem notificação de falha real** na Automation: os blocos `Output`/`Error` só exibem status e interrompem a execução — não há conector de e-mail/Slack/Teams alertando um responsável. Considerar adicionar se monitoramento ativo for necessário.
- ~~**Inconsistência no service name Oracle**~~ — **Revisado em 2026-07-23**: `di-oracle.md`/`da-oracle.md` usavam `192.168.1.27:1521/XEPDB1` como se fosse um valor fixo do projeto, mas em deploy real (tenant `br-qcda`) a fonte foi um Oracle dedicado diferente (`oracle-xe-br-qcda` via Docker). Esses arquivos são compartilhados entre tenants e **não são atualizados automaticamente** — agora trazem um aviso explícito marcando o `Server`/`Host name` como exemplo a confirmar por tenant, não uma constante confiável.
- **Scripts `ext001-3` são legado**: não fazem parte do deploy atual (substituídos por `str001` via CDC), mas permanecem no repositório — evitar reativá-los por engano.
- **Limitações do conector S3 V2** (sem suporte a wildcard) documentadas nos comentários de `str001_bronze_vendasods.qvs` — validar se persistem no tenant/conector novo antes de assumir que o workaround (listagem completa + filtro client-side) ainda é necessário.
- **Supplemental logging/ARCHIVELOG não habilitados por padrão**: em deploy real (2026-07-23), preparar o projeto de Data Integration falhou com `[SOURCE_UNLOAD]E: Minimal database supplemental logging level is not enabled [1020418]`. Os scripts de `base-dados/` não cobrem isso (é configuração de instância, não de usuário/schema) — precisa ser checado/habilitado manualmente antes do passo 6 do deploy. Ver 2.3 e [Guia_Instalacao_Projeto.md §2](Guia_Instalacao_Projeto.md#2-preparar-a-fonte-oracle-usuário-tabelas-e-dados-de-exemplo).
- **Autorização OAuth da Automation nem sempre necessária na prática**: em deploy real (2026-07-23), a Automation rodou com sucesso no primeiro disparo agendado sem nenhuma autorização OAuth manual no editor — o passo de autorização (Guia_Instalacao_Projeto.md passo 9) não é garantidamente bloqueante; tratar como algo a verificar, não como certeza.
- **Registro do MCP na prática é via conector do claude.ai, não `claude mcp add`**: em ambiente VS Code + conta claude.ai (deploy real, 2026-07-23), o registro foi um conector personalizado nas configurações do claude.ai, exigindo reiniciar o VS Code para aparecer disponível. Ver 2.7 (já atualizado para refletir esse caminho).
- **`dim_tempo` de `trf005_gold_star_schema.qvs` é uma dimensão conformada** (mistura Data_Venda + Data_Remessa + Data_Devolucao no mesmo calendário) — já levou a um diagnóstico errado de "data futura em vendas" quando na verdade era Data_Remessa/Data_Devolucao. Comentário de aviso adicionado direto no script (seção 4, construção de `dim_tempo`).
- **Nenhuma validação documentada de CDC pós-full-load** até 2026-07-23: em deploy real, o CDC processou o full load mas nenhuma mudança incremental (`totalProcessedCount: 0`) até isso ser checado manualmente. Item de checklist adicionado em [Guia_Instalacao_Projeto.md §10](Guia_Instalacao_Projeto.md#10-validação--smoke-test).
