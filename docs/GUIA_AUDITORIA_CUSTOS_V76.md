# V7.6 — Auditoria local e segura da Inteligência de Custos

O código de leitura reutiliza o módulo independente validado na branch `inteligencia-custos-2026`. Esta etapa NÃO integra uma API financeira, NÃO sincroniza dados com o Neon e NÃO modifica as planilhas XLSM.

A auditoria procura `BASE_DADOS_GERAL.xlsm` e os demais arquivos mapeados dentro de `C:\\Users\\Windows\\Music\\Sistema_Rateio\\CONDOMÍNIOS`. Todas as leituras usam somente `zipfile` e XML da biblioteca padrão do Python; macros VBA não são carregadas ou executadas. Antes de uma integração real, verificar as divergências e os direitos de acesso por condomínio.

## Windows (CMD)

1. Abra o **Prompt de Comando (CMD)**, não precisa mudar de branch nem abrir o Excel.
2. Execute:

```bat
curl.exe -fL --retry 2 "https://raw.githubusercontent.com/arthurvhoda-gif/Controladoria-app/push-pwa-v74-20261109/sincronizador/auditar_planilhas.py" -o "%USERPROFILE%\\Downloads\\auditar_planilhas_haize_v76.py"
```

3. Se o download terminou com sucesso, execute:

```bat
py -3 "%USERPROFILE%\\Downloads\\auditar_planilhas_haize_v76.py" --pasta "%USERPROFILE%\\Music\\Sistema_Rateio\\CONDOMÍNIOS" --saida "%USERPROFILE%\\Documents\\Haize_Auditoria_Custos_V76"
```

4. Ao final, leia `RESUMO_DA_AUDITORIA.txt` dentro da pasta `Documentos\\Haize_Auditoria_Custos_V76`.

Não compartilhe `divergencias.csv` publicamente, pois pode conter descrições, valores e IDs de lançamentos. Se precisar de ajuda com as divergências, envie somente os totais ou um trecho sem dados identificáveis.

A auditoria gera apenas três arquivos na pasta de saída: `RESUMO_DA_AUDITORIA.txt`, `resumo_por_condominio.csv` e `divergencias.csv`. Não escreve na pasta das planilhas e não tem requisições de rede. O primeiro comando acessa apenas o GitHub para baixar o script do próprio repositório.

## Testes automatizados

```bat
py -3 -m unittest testes_servicos.test_auditoria_custos_v76 -v
```

Todos os testes usam planilhas XLSM fictícias em diretórios temporários, sem acesso aos arquivos reais do usuário.
