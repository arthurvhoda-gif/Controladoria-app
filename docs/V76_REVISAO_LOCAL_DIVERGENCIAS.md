# V7.6 — Revisão local de divergências

Complementa o painel de Conciliação de Custos. Após carregar `resumo_por_condominio.csv`, a Controladoria pode selecionar `divergencias.csv` da mesma auditoria no navegador.

- Leitura somente no navegador, sem upload, sem registro no Neon e sem dados persistentes.
- Conferência cruzada de quantidades entre os arquivos por condomínio. Em caso de conflito, o relatório detalhado é rejeitado; os totais já importados permanecem na tela.
- Lista de tipos e contagem de ocorrências; filtros por tipo e condomínio.
- Identificadores e observações ficam ocultos até a Controladoria optar por exibi-los.
- Registros globais sem condomínio do resumo são sinalizados; não desaparecem silenciosamente.
- Nenhum comando de aprovação, correção, gravação em XLSM ou sincronização com o backend é adicionado.

Homologação: no site de testes como Controladoria, selecionar o resumo e o arquivo `C:\Users\Windows\Documents\Haize_Auditoria_Custos_V76\divergencias.csv`. Para a auditoria de 10/11/2026, o esperado é 19 ocorrências do tipo `NAO_ENCONTRADO_NA_BASE`, divididas em Max Living (8), Sunny Downtown (6), Polaris (5). Não enviar arquivos ao chat para esta etapa.

O checklist de validação em CI executa parser, filtro, compatibilidade de totais, CSV com vírgulas e aspas, e rejeição de arquivos incompatíveis.
