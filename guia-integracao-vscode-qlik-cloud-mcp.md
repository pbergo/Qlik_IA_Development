# Guia de integração: Claude Code (VS Code) com Qlik Cloud via MCP Server

Este documento descreve os passos básicos para conectar o Claude Code — extensão do Visual Studio Code — ao Qlik Cloud por meio de um servidor MCP (Model Context Protocol).

## 1. Pré-requisitos

- Conta ativa no Qlik Cloud
- Acesso a um servidor MCP compatível com Qlik Cloud
- Credenciais válidas para autenticação no Qlik Cloud (token, API key ou OAuth)
- Node.js ou Python instalados, dependendo do servidor MCP utilizado

## 2. Preparar o ambiente no Qlik Cloud

1. Acesse o tenant do Qlik Cloud.
2. Crie ou identifique um usuário/service account com permissões para os recursos que você quer acessar.
3. Gere as credenciais necessárias para o Qlik Cli:
    1. Cliente OAuth: https://qlik.dev/authenticate/oauth/create/create-oauth-client/
    1. Anote os valores de:
        1. URL do tenant do Qlik Cloud
        1. ID do cliente / segredo (se aplicável)
        1. Escopo de permissão necessário

## 3. Instalar o Claude Desktop

##### Instalação
Para instalar o Claude Desktop no Windows, siga este passo a passo rápido:
1. Baixar o Instalador Oficial (https://claude.com/download)
2. Executar a Instalação
3. Fazer Login e Usar
* Assim que a instalação terminar, o aplicativo abrirá de forma automática. Caso contrário, procure por Claude no menu Iniciar do Windows.
* Clique em entrar e faça login com a sua conta da Anthropic. O sistema abrirá uma aba rápida no navegador para autenticar o acesso com segurança. 
4. Configurar o MCP no Claude
- Do lado inferior esquerdo, clique no seu nome
- Em seguida vá em Configurações (Settings)
- Selecione a esquerda Personalizar --> Conectores
- Clique em Adicionar --> Adicionar conector personalizado
- Entre com o nome para conector, como QlikMCP.
- Na URL Remota, adicione: https://[tenant URL]/api/ai/mcp.
    p.ex. https://pbergo-qcda.us.qlikcloud.com/api/ai/mcp
- Em Configurações Avançadas --> OAuth Client ID, informe - 76d3f46e87655a50424bec7e0f0bb1e2.
- E deixe os outros campos em branco.
- Clique em adicionar
- Agora na lista de conectores, clique em Conectar
- Faça o login no Qlik Cloud tenant e 
- Click Aprovar.

** Nota: o usuário do tenant deve ser o mesmo do Claude !

##### Requisitos Mínimos do Sistema
* Sistema Operacional: Windows 10 (Build 19041 ou superior) ou Windows 11.
* Privilégios: É altamente recomendável instalar com uma conta de administrador para garantir o funcionamento correto de recursos avançados, como o agente autônomo Claude Cowork.


## 4. Instalar Visual Studio Code e extensões

##### Instalação
O Visual Studio Code é nossa IDE a ser utilizada para realizar os desenvolvimentos.

1. Baixe o instalador [Visual Studio Code System](https://go.microsoft.com/fwlink/?linkid=852157) para Windows.
1. Execute o instalador com permissões de administrador.

O instalador System disponibiliza o VS Code para todos os usuários da máquina.

##### Extensões

Adicione a extensão do Claude
- [Claude Code for VS Code](#anthropic.claude-code)

Algumas extensões do Visual Studio code são muito úteis:

- [Markdown Preview Enhanced](#shd101wyy.markdown-preview-enhanced)
- [Ctrl-Q QVD Viewer](#ptarmiganlabs.ctrl-q-qvd-viewer)
- [Rainbow CSV](#mechatroner.rainbow-csv)

## 5. Instalar o Qlik CLI

O Qlik CLI é útil para autenticar, validar e interagir com recursos do Qlik Cloud a partir do terminal. O processo pode variar conforme a distribuição disponibilizada pela sua organização, mas os passos básicos são:

1. Faça o download o último pacote em [qlik-Windows-x86_64.zip from GitHub](#https://github.com/qlik-oss/qlik-cli/releases).
1. Descompact o arquivo qlik-Windows-x86_64.zip baixado.
1. Mova o arquivo qlik.exe para uma localização que você possa executar. p.ex. Windows/System32.
1. Confirme que o diretório está na variável PATH do seu ambiente.
1. Abra um novo terminal e valide a instalação:

```powershell
qlik --version
```

## 6. Configurar a extensão Claude Code para usar o MCP Server

O Claude Code gerencia servidores MCP e fica integrado diretamente ao Claude Desktop, mas para isso, execute os passos a seguir.

1. Abra o Visual Studio Code e verifique se a extensão já está instalada
1. Acesse o ícone do Claude na paleta de botões a esquerda
1. Ao ser perguntado como quer utilizar o Claude
    1. Selecione Claude.ai Subscription, se tiver uma assinatura válida.
    1. Select Anthropic Console, se tiver assinatura de uso de APIs.
1. Selecione abrir o site do Claude
1. Faça o login com sua conta e autorize o aplicativo

Pronto, agora irá aparecer o ícone to Claude ao load direito superior.

## 7. Validar a conexão com o Qlik Cloud

Reinicie o Visual Studio Code e talvez até o computador, teste a integração com uma solicitação simples no chat do Claude Code e em seguida no Visual Studio.

Exemplos de validação:

- Listar espaços ou aplicativos do Qlik Cloud
- Consultar metadados de uma app
- Buscar uma expressão ou objeto do ambiente

Exemplo de prompt:

```text
Conecte-se ao Qlik Cloud e liste os espaços disponíveis.
```
Se tudo estiver correto, o servidor MCP deverá responder com os dados do ambiente conectado, e as ferramentas do Qlik Cloud aparecerão disponíveis para o Claude Code usar durante a conversa.

## 8. Boas práticas

- Mantenha os segredos e tokens fora do repositório; use variáveis de ambiente do sistema em vez de valores fixos no código
- Revise as permissões do usuário/service account para evitar acesso indevido.
- Atualize o servidor MCP e as credenciais periodicamente.
- Monitore logs para identificar problemas de autenticação ou conexão.
- Mude para modelos mais simples e só use os mais complexos, que tem alto consumo de tokens e créditos para situações difíceis.
- Use o repositório GitHub e integre o Visual Studio Code.

