This file contains information to connect to source database through Qlik Data Analytics: 

⚠️ Este arquivo é compartilhado entre deploys/tenants e NÃO é atualizado automaticamente — o `Host name` abaixo é um EXEMPLO/snapshot de um deploy específico. Confirmar/atualizar por tenant — ver o mesmo aviso em [di-oracle.md](di-oracle.md). Nota: este é o conector (`da-*`, via Direct Access Gateway) usado diretamente pelos scripts de extração `ext00x` deste projeto.

space: $shared-space$
Data gateway: "QDAG_VendasODS"
Connector: "Oracle (via Direct Access gateway)"
Name: "da-oracle"
Host name: "192.168.1.27:1521/XEPDB1"  # EXEMPLO — confirmar/atualizar por tenant, ver aviso acima
Schema: "vendasods"
User name: $source-db-user$
Password: $source-db-password$
