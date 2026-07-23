# Requisitos Técnicos — Automation `VendasODS_Pipeline_Execution`

> Levantado a partir do tenant `pbergo-qcda.us.qlikcloud.com` via `qlik-cli` em 2026-07-23.
> Automation ID: `eb5be3eb-5605-4cf5-ac93-1fac80830470`
> Definição completa: [VendasODS_Pipeline_Execution.json](VendasODS_Pipeline_Execution.json)

## 1. Tenant / Licenciamento

- Qlik Cloud tenant com módulo **Qlik Application Automation** habilitado (consome "Automation minutes" do plano).
- Cota de minutos de automação suficiente para a carga de execução:
  - Duração média de uma execução completa: **~5 min** (última execução: 14:15:17 → 14:20:24, 307s).
  - Frequência do schedule: a cada **15 minutos** (`RRULE:FREQ=MINUTELY;INTERVAL=15`).
  - Consumo estimado: ~20 min de automação por hora (~480 min/dia).
- `maxConcurrentRuns: 1` — a duração real (~5 min) precisa manter folga confortável dentro da janela de 15 min para não gerar runs enfileirados/sobrepostos.
- Timezone do schedule: `America/Sao_Paulo` — confirmar que é o fuso correto para o negócio.

## 2. Permissões do usuário/owner da automation

- Owner atual da automation: `ownerId 6a4812b1dd31bf428a7e245b`.
- Esse usuário (ou quem assumir a posse) precisa de:
  - Permissão para criar/editar Automations no tenant.
  - Papel `producer` (ou `codeveloper`) no espaço **VendasODS_Shared** (`spaceId 681f830ee2e164faaaff97d0`, tipo `shared`) — necessário para ter privilégio `reload` nos 7 apps do pipeline.

## 3. Conector "Qlik Cloud Services"

- Todas as 7 etapas de reload usam o snippet padrão **Qlik Cloud Services – Do Reload** (`snippet_guid: b5dbb7a0-e715-11ea-b2bf-43bb35adee19`), via conector `connectorId: 61a87510-c7a3-11ea-95da-0fb0c241e75c`.
- Requer uma **conexão OAuth ativa** desse conector configurada dentro do editor de Automations (gerenciada pelo Automations, não pelo `qlik data-connection`), autorizada por um usuário com permissão de reload em todos os apps abaixo.

## 4. Apps do pipeline

Todos residem no espaço **VendasODS_Shared** (`681f830ee2e164faaaff97d0`), não publicados.

| Ordem | Etapa | App | App ID |
|---|---|---|---|
| 1 | str001 | str001_bronze_vendasods | `698a0ca1-87e9-4d62-9c77-9316dce35a74` |
| 2 | trf001 | trf001_silver_vendasods | `ce097cdb-59c2-4ca3-9c40-0f091be1436f` |
| 3 | trf002 | trf002_silver_devolucoes | `3e7ffeff-93b6-4408-b474-93144499d145` |
| 4 | trf003 | trf003_silver_vendas | `f83da235-4933-4bfc-9648-f0882c904845` |
| 5 | trf004 | trf004_silver_devolucoes_consolidado | `35a3c2c1-0476-418a-94b1-0a734d4bc8dd` |
| 6 | trf005 | trf005_gold_star_schema | `75f2b721-8fe1-4100-a766-a228b45db0fb` |
| 7 | viz001 | viz001_vendasods_analytics | `2ca71208-e9f4-4ddd-9e34-8c377a14c4fa` |

- Cada etapa só é disparada se a etapa anterior retornar `status = SUCCEEDED`; qualquer falha interrompe a cadeia (`ErrorBlock` com `action: stop`).
- Todos os 7 apps precisam existir, estar acessíveis pelo owner da automation, e seus scripts de carga precisam rodar sem erro isoladamente.

## 5. Conexões de dados (usadas pelos scripts de carga)

Referência: [data-connections/da-s3.md](../data-connections/da-s3.md)

| Nome | Connector | Região | Bucket |
|---|---|---|---|
| `VendasODS_Shared:da-s3` | `File_AmazonS3ConnectorV2` (storage provider) | `us-west-2` | `qmi-bucket-68b823035b598a2f0f6af8f6` |
| `VendasODS_Shared:da-s3-metadata` | `AmazonS3ConnectorV2` (web connector) | `us-west-2` | `qmi-bucket-68b823035b598a2f0f6af8f6` |

- Usadas em cascata por todas as camadas:
  - `str001` grava a camada Bronze (`materlake/bronze/`).
  - `trf001`–`trf005` leem/gravam Silver e Gold (`materlake/silver/silver001/`, `materlake/gold/`).
  - `viz001` lê a camada Gold para análise.
- As credenciais AWS associadas a essas duas conexões (`Access Key` / `Secret Key`, ver `$di-s3-accesskey$` / `$di-s3-secretkey$` em [data-connections/da-s3.md](../data-connections/da-s3.md)) precisam estar válidas e com permissão de leitura/escrita no bucket e nos prefixos acima. Sem isso, `str001` (que grava) e as demais etapas (que leem/gravam) falham.

## 6. Lacunas / recomendações (não bloqueantes para execução, mas relevantes)

- **Sem notificação de falha real**: os blocos `Output`/`Error` apenas exibem o status e interrompem a automation — não há conector de e-mail/Slack/Teams alertando um responsável. Se monitoramento ativo for requisito do negócio, precisa ser adicionado à automation.
- **`executionToken` sensível no JSON exportado**: o arquivo [VendasODS_Pipeline_Execution.json](VendasODS_Pipeline_Execution.json) contém um `executionToken` (segredo de trigger via webhook) em texto plano. Como esse arquivo é versionado no repositório, recomenda-se **não commitar o token real** (remover/mascarar o campo antes do commit ou tratar o arquivo como sensível), já que qualquer pessoa com acesso ao repo poderia disparar a automation externamente com ele.
