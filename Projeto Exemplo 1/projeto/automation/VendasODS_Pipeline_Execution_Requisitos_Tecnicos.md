# Requisitos Técnicos — Automation `VendasODS_Pipeline_Execution`

> Este projeto (Projeto Exemplo 1) usa extração direta via SQL (scripts `ext001`/`ext002`/`ext003`, conexão `da-oracle`, Direct Access Gateway) em vez de CDC/Data Movement Gateway. A Automation abaixo é um **template**, ainda não implantado em nenhum tenant — os campos entre `<>` (App IDs, Automation ID, Space ID, Owner ID, Schedule ID, `executionToken`) precisam ser preenchidos durante a instalação, seguindo [Guia_Instalacao_Projeto.md](../../implantacao/Guia_Instalacao_Projeto.md).
> Definição completa: [VendasODS_Pipeline_Execution.json](VendasODS_Pipeline_Execution.json)

## 1. Tenant / Licenciamento

- Qlik Cloud tenant com módulo **Qlik Application Automation** habilitado (consome "Automation minutes" do plano).
- Cota de minutos de automação suficiente para a carga de execução (9 etapas em cascata — mais etapas que o pipeline CDC do Projeto Exemplo 2, já que a extração aqui é feita em 3 scripts separados por tabela em vez de 1 único `str001`).
  - Frequência do schedule: a cada **15 minutos** (`RRULE:FREQ=MINUTELY;INTERVAL=15`) — ajustar conforme o volume de dados e o tempo real de execução observado no tenant de destino.
- `maxConcurrentRuns: 1` — a duração real de uma execução completa precisa manter folga confortável dentro da janela do schedule para não gerar runs enfileirados/sobrepostos.
- Timezone do schedule: `America/Sao_Paulo` — confirmar que é o fuso correto para o negócio.

## 2. Permissões do usuário/owner da automation

- O usuário dono da automation precisa de:
  - Permissão para criar/editar Automations no tenant.
  - Papel `producer` (ou `codeveloper`) no espaço **VendasODS_Shared** — necessário para ter privilégio `reload` nos 9 apps do pipeline.

## 3. Conector "Qlik Cloud Services"

- Todas as 9 etapas de reload usam o snippet padrão **Qlik Cloud Services – Do Reload** (`snippet_guid: b5dbb7a0-e715-11ea-b2bf-43bb35adee19`), via conector `connectorId: 61a87510-c7a3-11ea-95da-0fb0c241e75c`.
- Requer uma **conexão OAuth ativa** desse conector configurada dentro do editor de Automations, autorizada por um usuário com permissão de reload em todos os apps abaixo.

## 4. Apps do pipeline

Todos residem no espaço **VendasODS_Shared**, não publicados. Ordem de execução (cada etapa só é disparada se a anterior retornar `status = SUCCEEDED`; qualquer falha interrompe a cadeia):

| Ordem | Etapa | App | Script fonte |
|---|---|---|---|
| 1 | ext001 | ext001_cadastros | [../scripts/ext001_cadastros.qvs](../scripts/ext001_cadastros.qvs) |
| 2 | ext002 | ext002_pedidos_peditem | [../scripts/ext002_pedidos_peditem.qvs](../scripts/ext002_pedidos_peditem.qvs) |
| 3 | ext003 | ext003_devolucoes | [../scripts/ext003_devolucoes.qvs](../scripts/ext003_devolucoes.qvs) |
| 4 | trf001 | trf001_silver_vendasods | [../scripts/trf001_silver_vendasods.qvs](../scripts/trf001_silver_vendasods.qvs) |
| 5 | trf002 | trf002_silver_devolucoes | [../scripts/trf002_silver_devolucoes.qvs](../scripts/trf002_silver_devolucoes.qvs) |
| 6 | trf003 | trf003_silver_vendas | [../scripts/trf003_silver_vendas.qvs](../scripts/trf003_silver_vendas.qvs) |
| 7 | trf004 | trf004_silver_devolucoes_consolidado | [../scripts/trf004_silver_devolucoes_consolidado.qvs](../scripts/trf004_silver_devolucoes_consolidado.qvs) |
| 8 | trf005 | trf005_gold_star_schema | [../scripts/trf005_gold_star_schema.qvs](../scripts/trf005_gold_star_schema.qvs) |
| 9 | viz001 | viz001_vendasods_analytics | [../scripts/viz001_vendasods_analytics.qvs](../scripts/viz001_vendasods_analytics.qvs) |

- Todos os 9 apps precisam existir, estar acessíveis pelo owner da automation, e seus scripts de carga precisam rodar sem erro isoladamente antes de importar/ativar a automation.
- Ao importar o JSON, substituir cada `<APP_ID_...>` pelo App ID real criado no tenant de destino (ver [Guia_Instalacao_Projeto.md](../../implantacao/Guia_Instalacao_Projeto.md)).

## 5. Conexões de dados (usadas pelos scripts de carga)

Referência: [implantacao/data-connections/da-oracle.md](../../implantacao/data-connections/da-oracle.md), [da-s3.md](../../implantacao/data-connections/da-s3.md)

| Nome | Connector | Uso |
|---|---|---|
| `VendasODS_Shared:da-oracle` | Oracle (via Direct Access Gateway) | Fonte dos scripts `ext001`/`ext002`/`ext003` |
| `VendasODS_Shared:da-s3` | `File_AmazonS3ConnectorV2` | Bronze/Silver/Gold — usada por todas as 9 etapas |

- As credenciais Oracle (`ext00x`) e AWS (`da-s3`) precisam estar válidas e com permissão adequada nos schemas/prefixos usados. Sem isso, as etapas correspondentes falham.

## 6. Lacunas / recomendações (não bloqueantes para execução, mas relevantes)

- **Sem notificação de falha real**: os blocos `Output`/`Error` apenas exibem o status e interrompem a automation — não há conector de e-mail/Slack/Teams alertando um responsável. Se monitoramento ativo for requisito do negócio, precisa ser adicionado à automation.
- **`executionToken` sensível**: o campo `executionToken` no JSON é um segredo de trigger via webhook. **Nunca commitar o valor real** — o placeholder `<EXECUTION_TOKEN - GERAR NO DEPLOY, NUNCA COMMITAR O VALOR REAL>` deve ser substituído apenas localmente/no tenant, nunca no repositório.
- **Mais etapas que o pipeline CDC**: como a extração é feita por 3 scripts separados (`ext001`/`ext002`/`ext003`) em vez de 1 único `str001`, o pipeline tem 9 etapas em vez das 7 do Projeto Exemplo 2 — considerar o tempo total de execução ao definir a frequência do schedule.
