# HAIZE — Relatório consolidado de qualidade V7.0

**Data:** 06/11/2026  
**Branch:** `estabilizacao-v70-20261106`  
**PR:** https://github.com/arthurvhoda-gif/Controladoria-app/pull/2  
**Bateria de referência:** https://github.com/arthurvhoda-gif/Controladoria-app/actions/runs/42228961337

## Evidência de execução automatizada

| Frente | Resultado comprovado |
|---|---|
| Backend Python (SQLite isolado) | **199 testes aprovados** |
| Navegador Chromium (API totalmente fictícia) | **6 testes aprovados** |
| React | `npm ci`, `npm run build` e `npm run lint` aprovados |
| Git / novos artefatos locais | Scanner aprovado; **6 arquivos legados ainda sinalizados** |
| PostgreSQL 16 descartável | Schema criado, rotinas automáticas de migração executadas duas vezes, dados fictícios incluídos, backup `pg_dump` gerado, restauração em outro banco e integridade conferida |
| Dependências npm | Auditoria executada e inventário produzido; **não** significa que vulnerabilidades foram resolvidas |

Os testes rodam automaticamente nas alterações da branch e no PR. Nenhum teste depende de credenciais de produção. Os testes do navegador bloqueiam service workers, usam API simulada e não enviam e-mails ou WhatsApp.

## Escopo efetivamente coberto

1. Login real via HTTP, token JWT, token inválido, isolamento de contas com nomes iguais, pedidos legados sem identificação e bloqueio de rotas indevidas.
2. Perfis Controladoria, Solicitante, Checklist e Financeiro, isolamento de condomínios, leitura de comprovantes, proibição de alterações pelo Financeiro.
3. Fluxos de serviço, eventos, participantes, fotografias, consentimentos WhatsApp e prévias, pagamentos, estornos, alertas de excedentes, avisos e rastreabilidade — cenários executados pela suíte Python, conforme os respectivos testes.
4. Telas Chromium: autenticação, logout, sessão expirada, paginação e filtros, zelador, Financeiro somente consulta, navegação entre módulos e prévias de WhatsApp.
5. Anexos de compras e fotos de checklist: proteção contra caminhos maliciosos, tamanho máximo, limpeza de arquivos parcialmente gravados, acesso por permissão, preservação de downloads legados.
6. `scripts/inventariar_arquivos_v70.py --somente-leitura`: inventário de quantidades presentes/ausentes sem ler conteúdo de arquivos ou imprimir nomes/caminhos; a função de contagem tem testes automatizados. **Não foi executado contra produção.**

## Achados de segurança ainda abertos

- `npm audit` identificou **16 vulnerabilidades** no conjunto instalado (6 altas, 7 moderadas, 3 baixas). Auditando somente dependências não-dev, são **12** (5 altas, 4 moderadas, 3 baixas). A lista inclui `xlsx` com vulnerabilidade alta sem correção automática disponível. Não usar `npm audit fix --force` nem remover a exportação XLSX; planejar substituição compatível e testes das planilhas.
- Há **6 artefatos legados versionados** (`backend/controladoria.db` e cinco `.pyc`). Não foram apagados; é necessária avaliação de dados sensíveis e eventual remediação do histórico público.
- Anexos de compras e fotos do checklist **continuam no armazenamento local/efêmero da API**. Uploads novos foram protegidos, mas ainda precisam de armazenamento durável e migração dos anteriores.
- Rotação coordenada das credenciais expostas anteriormente: `AUTOMATION_SECRET` entre Render e GAS, e `HAIZE_SECRET` separadamente para não quebrar os PDFs.
- A migração V6.8/V6.9 no banco **real** Neon ainda não foi ensaiada sobre cópia restaurada dos dados reais. O teste PostgreSQL descartável valida o esquema e o processo de backup/restauração com dados inventados; não garante a migração de todos os legados reais.
- A homologação funcional em servidor de testes com banco e usuários de teste continua necessária para uploads, pagamentos, concorrência, sessões, relatórios e notificações. Testes com API simulada não substituem essa verificação.

## Critério de saída desta etapa

**Etapa de automação dos testes: concluída para a V7.0 em branch isolada.** A bateria foi implantada, executada e ficou verde. O job de auditoria npm **apenas emite diagnóstico**, por isso o workflow verde **não significa segurança aprovada**.

**Publicação/aceite integral do aplicativo: ainda bloqueado** pelos riscos de segurança, persistência e migração listados acima. O PR permanece em rascunho; não fazer merge ou deploy em `main` sem plano de produção, backup verificado, homologação e decisão explícita.

A ordem de trabalho após o fechamento desta bateria é: (1) corrigir vulnerabilidades sem perder XLSX, (2) migrar uploads para persistência durável com inventário e validação de cópia, (3) ensaiar migração de produção a partir de cópia do Neon, (4) homologar no ambiente de teste e liberar produção em etapas.
