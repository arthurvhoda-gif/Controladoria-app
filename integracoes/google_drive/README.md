# V7.2 — ponte Drive em homologação

Estado: ponte Apps Script implementada; 13 testes locais com serviços Google simulados aprovados. Backend, transporte HTTPS, quotas, capacidade, backup/restauração e persistência após deploy ainda não homologados. Nenhuma alteração no Render, Neon, e-mails ou produção.

## Instalação guiada
No projeto separado HAIZE_Armazenamento_TESTES_V72, substituir Código.gs pelo conteúdo integral de ArmazenamentoV72.gs. Manter as propriedades HAIZE_STORAGE_FOLDER_ID e HAIZE_STORAGE_SECRET (64 caracteres hexadecimais gerados com secrets.token_hex(32)). Pasta HAIZE_APP_TESTES_V72 restrita, sem editores ou leitores adicionais. Executar validarPonteV72 no editor. O teste cria e mantém um arquivo fictício; não remove dados anteriores. Não implantar ainda.

## Protocolo para o futuro cliente backend
POST JSON com payload (string JSON UTF-8) e signature (HMAC-SHA256 hexadecimal do payload exato, com a chave textual da propriedade). Payload: version=1, ts=Unix segundos com tolerância de 300 segundos, op=ping/put/get. put/get usam key hexadecimal de 32 caracteres gerada pelo backend. put exige size, sha256 dos bytes e data em base64 canônico. Máximo 20 MiB por arquivo; limites específicos de cada módulo continuam sob responsabilidade do backend. Não enviar a chave em URLs ou logs. Nunca confiar em HTTP 200 sozinho: conferir ok e validar tamanho/hash do download no backend.

As operações são repetíveis dentro da janela de tempo: put não sobrescreve, e a mesma chave com conteúdo diferente retorna CONFLITO. Não há proteção de nonce único: repetição de uma solicitação assinada válida é admitida, de forma idempotente. Só o backend deve possuir o segredo e deve autorizar usuário/condomínio antes de cada chamada. Não expor esta ponte diretamente ao frontend. A busca usa apenas nomes opacos na pasta configurada, não aceita IDs arbitrários de arquivo.

A ponte não oferece delete: remoção e coleta de órfãos exigem uma etapa posterior auditável, para não apagar evidências durante falhas parciais. Uma criação cujo retorno falhe pode ser recuperada repetindo a mesma chave. Não compartilhar nem editar manualmente arquivos da pasta. Alterações externas ao script não são protegidas pelo lock.

## Limites ainda a validar
Apps Script tem quotas e limites de execução; HMAC não impede consumo de execução por solicitações inválidas ao endpoint público. A franquia do Drive é finita e compartilhada com outros produtos da conta. Não há promessa de gratuidade ilimitada ou SLA. Não há compactação implementada nesta ponte: ela preserva os bytes recebidos. 50 fotos/dia é estimativa de dimensionamento, não limite diário. Armazenamento persistente não substitui backup independente.

## Testes locais
node --test testes_armazenamento/test_ponte_v72.cjs

O teste usa mocks de Drive, Properties, Lock, Utilities e ContentService. Ele não comprova acesso Google real, restrições herdadas de pastas, transporte HTTPS, desempenho ou preservação após reinício do Render. Essas verificações devem ocorrer antes da aprovação da V7.2. O autoteste do editor testa o Drive real, mas não o transporte HTTP.
