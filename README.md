# Qlik IA Development

## Visão geral

Um repositório abrangente demonstrando como aproveitar a Inteligência Artificial e práticas modernas de engenharia de dados no Qlik Cloud. Este projeto apresenta implementações completas de pipelines de dados usando arquitetura medalhão, da ingestão de dados até a análise, com exemplos de integração para o VS Code e templates práticos de projeto.

## Conteúdo

- [Guia de Integração com o VS Code](guia-integracao-vscode-qlik-cloud-mcp.md) — Configure o VS Code com o Qlik Cloud usando servidores MCP para um desenvolvimento integrado.

### Exemplos

- [Projeto Exemplo 1: Pipeline básico de dados de vendas](./Projeto%20Exemplo%201/README.md) — Um exemplo fundamental de engenharia de dados usando Oracle como origem, implementando a arquitetura medalhão (camadas bronze, silver, gold) com dados armazenados no Amazon S3 e análise no Qlik Cloud. Isso tudo usando scripts Qlik para extrair e transformar os dados em arquivos parquet.

- [Projeto Exemplo 2: Pipeline avançado baseado em CDC](./Projeto%20Exemplo%202/README.md) — Uma implementação estendida de engenharia de dados, onde a extração usa o método CDC - Change Data Capture para movimentar os dados para o Amazon S3, implementando a arquitetura medalhão (camadas landing, bronze, silver e gold), usando o Data Movement Gateway e também os scripts Qlik para a ingestão e transformações.

### Como usar 

Comece instalando o Claude Code, depois adicione este diretório a ele e simplesmente pergunte: Como implementar o Projeto 2?


