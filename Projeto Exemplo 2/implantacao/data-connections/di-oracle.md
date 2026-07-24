This file contains information to connect to source database through Qlik Data Integration: 

⚠️ Este arquivo é compartilhado entre deploys/tenants e NÃO é atualizado automaticamente — o `Server` abaixo é um EXEMPLO/snapshot de um deploy específico (não uma constante do projeto). Antes de usar em um novo tenant, confirmar o host/porta/service real da fonte Oracle daquele ambiente (ver [Guia_Implementacao_Novo_Tenant.md §2.3](../Guia_Implementacao_Novo_Tenant.md#23-conectividade-com-a-fonte-de-dados-oracle)) e atualizar o valor abaixo — ex. pode ser uma instância dedicada via Docker (`oracle-xe-<tenant>`, ver Apêndice A.1 do Guia de Instalação) em vez do host fixo mostrado aqui.

space: $data-space$
Data gateway: "QDMG_VendasODS"
Connector: "Oracle"
type: "source"
Name: "di-oracle"
Cloud provider: "None"
Server: "192.168.1.27:1521/XEPDB1"  # EXEMPLO — confirmar/atualizar por tenant, ver aviso acima
Schema: "vendasods"
User name: $source-db-user$
Password: $source-db-password$
