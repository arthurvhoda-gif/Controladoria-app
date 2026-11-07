# Controladoria Haize — Demonstração local das notificações V7.3

## O que é
Um modo de **demonstração da aplicação real** (React + FastAPI), sem a
infraestrutura da produção: usa exclusivamente um SQLite **temporário** com
contas, condomínios e tarefa **fictícios**. Nenhum dado real é importado.

O processo roda em `127.0.0.1` (acessível apenas no seu computador).
A interface exibe **DEMONSTRAÇÃO LOCAL — DADOS FICTÍCIOS**.

## Como iniciar no Windows (CMD)

Depois de obter a branch `notificacoes-v73-20261107`:

```cmd
cd /d "C:\Users\Windows\Documents\Controladoria-V72" && git pull --ff-only origin notificacoes-v73-20261107 && scripts\iniciar_demo_local_v73.cmd
```

- O script verifica Python e Node/npm já disponíveis.
- Prepara **ambiente Python separado** em `.venv_demo_v73`; a primeira
  instalação pode baixar bibliotecas gratuitas do Python Package Index.
- Reutiliza as dependências do frontend instaladas via `npm ci`, ou as
  instala pelo lockfile se necessário.
- Abre `http://127.0.0.1:5174` no navegador padrão.
- Exibe e-mails e senha **fictícios** de demonstração no CMD.
- **Para encerrar, volte ao CMD e pressione Ctrl+C.**
- O banco de dados, os anexos e as fotografias temporários são descartados
  ao encerrar a demonstração. O ambiente Python instalado pode permanecer
  para reutilização, mas é ignorado pelo Git.

### Contas de demonstração (não usar na produção)

| Papel | E-mail |
| --- | --- |
| Controladoria | `gestora.demo@local.test` |
| Zelador Alfa | `zelador.alfa.demo@local.test` |
| Zelador Beta | `zelador.beta.demo@local.test` |

Senha fictícia, igual nas três: `SenhaFicticiaDeTeste123`.

O zelador Alfa recebe uma tarefa fictícia na Central de Serviços. O
zelador Beta não deve conseguir ver nem abrir essa tarefa. Os avisos
internos, a leitura e o isolamento são processados pela **API real** em
um banco descartável.

## Barreiras de segurança

- O processo configura `DATABASE_URL` para arquivo SQLite dentro de um
  diretório temporário **criado pelo próprio lançador**; não recebe a URL
  Neon nem reutiliza banco da instalação existente.
- Descarta configurações herdadas de Render, Google Drive, Resend, GAS e
  outros serviços externos ao preparar ambiente de execução.
- `HAIZE_STORAGE_MODE=local`, uploads dentro da pasta temporária.
- E-mails automáticos desligados; nenhum despachante WhatsApp foi
  implementado. Nenhuma mensagem real é enviada.
- A demonstração remove o import externo das fontes Google **somente
  nesse modo**. A aparência normal/produção não é modificada.
- Não é ambiente de produção nem serviço hospedado. Não se deve publicar
  `backend/demo_local_v73.py` em servidor externo.
- Qualquer modificação de código fica na branch de desenvolvimento; o
  comando não modifica `main`, Render, Vercel ou Neon.

## Verificação automática
O GitHub Actions executa, além de Python, React, Chromium e PostgreSQL
descartável, o script `scripts/ensaio_demo_local_v73.py` que testa o modo
local **sem mocks HTTP** e intercepta requisições externas do navegador.
A homologação real em Windows só fica confirmada depois que o atalho
for executado no computador do usuário.

## Limites do teste
A demonstração confirma integração e isolamento; não mede desempenho do
ambiente implantado nem substitui implantação em homologação separada.
O WhatsApp oficial permanece sem despacho, conta ou orçamento contratado.
