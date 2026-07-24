This file contains information to connect to source database through Qlik Data Analytics: 

⚠️ Este arquivo é compartilhado entre deploys/tenants e NÃO é atualizado automaticamente — o `Host name` abaixo é um EXEMPLO/snapshot de um deploy específico. Confirmar/atualizar por tenant — ver o mesmo aviso em [di-oracle.md](di-oracle.md) e [Guia_Implementacao_Novo_Tenant.md §2.3](../Guia_Implementacao_Novo_Tenant.md#23-conectividade-com-a-fonte-de-dados-oracle). Nota: este conector (`da-*`, via Direct Access Gateway) é a via legada usada pelos scripts `ext00x` — não faz parte do pipeline CDC atual (ver `di-oracle.md`).

space: $shared-space$
Data gateway: "QDAG_VendasODS"
Connector: "Oracle (via Direct Access gateway)"
Name: "da-oracle"
Host name: "192.168.1.27:1521/XEPDB1"  # EXEMPLO — confirmar/atualizar por tenant, ver aviso acima
Schema: "vendasods"
User name: $source-db-user$
Password: $source-db-password$
