# -*- coding: utf-8 -*-
"""V7.6: reconcilia, por totais, despesas de origem ausentes da base geral.

SOMENTE LEITURA dos arquivos XLSM. Sem macros, banco ou rede.
Nenhum identificador, descricao de gasto ou valor individual e impresso.
A comparacao de atributos sugere possiveis correspondencias, nao prova duplicatas.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import importlib.util
import sys

PASTA = Path(r"C:\Users\Windows\Music\Sistema_Rateio\CONDOMÍNIOS")
AUDITOR = Path.home() / "Downloads" / "auditar_planilhas_haize_v76.py"


def carregar(caminho):
    if not caminho.is_file():
        raise FileNotFoundError("Auditor base ausente: " + str(caminho))
    spec = importlib.util.spec_from_file_location("haize_auditor_v76", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def assinatura(item, canon):
    return (canon(item["descricao"]), canon(item["categoria"]),
            item["data"], item["valor"])


def analisar(pasta, auditor):
    if not pasta.is_dir():
        raise FileNotFoundError("Pasta de origem ausente: " + str(pasta))
    mapa, base, _, duplicados = auditor.extrair_base(pasta / "BASE_DADOS_GERAL.xlsm")
    if duplicados:
        raise ValueError("Existem IDs duplicados na base geral; ver auditoria anterior.")
    if len(mapa) != 10:
        raise ValueError("Esperava 10 condominios cadastrados, achei %d." % len(mapa))
    nomes = [auditor.canon(nome) for nome, _ in mapa]
    if len(set(nomes)) != 10:
        raise ValueError("Condominios repetidos na base geral.")
    origem = []
    for nome, arquivo in mapa:
        p = pasta / arquivo
        if not p.is_file():
            raise FileNotFoundError("Arquivo de condominio ausente: " + arquivo)
        c = auditor.extrair_condominio(p, nome)
        if c["sem_id"] or c["duplicados"] or c["valores_invalidos"] or c["datas_invalidas"]:
            raise ValueError("Existem erros nas despesas classificadas de " + nome + ". Ver auditoria.")
        itens_base = [(uid, it) for uid, it in base.items()
                      if auditor.canon(it["condominio"]) == auditor.canon(nome)]
        ids_locais = {uid for uid, _ in itens_base}
        faltantes = [(uid, item) for uid, item in c["classificadas"].items()
                     if uid not in ids_locais]
        if not faltantes:
            continue
        capacidade_exata = Counter(assinatura(it, auditor.canon) for _, it in itens_base)
        capacidade_valor = Counter((it["data"], it["valor"]) for _, it in itens_base)
        # Reserva uma unica correspondencia por registro da base para nao
        # classificar diversas despesas distintas como o mesmo lancamento.
        classificacoes = Counter()
        para_valor = []
        for uid, item in faltantes:
            id_global = base.get(uid)
            if id_global is not None:
                classificacoes["ID em outro condominio"] += 1
                continue
            chave = assinatura(item, auditor.canon)
            if capacidade_exata[chave] > 0:
                classificacoes["Possivel duplicata com outro ID"] += 1
                capacidade_exata[chave] -= 1
                capacidade_valor[(item["data"], item["valor"])] -= 1
                continue
            para_valor.append(item)
        for item in para_valor:
            chave = (item["data"], item["valor"])
            if capacidade_valor[chave] > 0:
                classificacoes["Mesmo valor e competencia"] += 1
                capacidade_valor[chave] -= 1
            else:
                classificacoes["Sem correspondencia identificada"] += 1
        meses_faltantes = Counter(it["data"][:7] for _, it in faltantes)
        meses_base = Counter(it["data"][:7] for _, it in itens_base if it["data"])
        meses = sorted(set(meses_faltantes))
        origem.append({
            "condominio": nome,
            "quantidade": len(faltantes),
            "classificacoes": dict(classificacoes),
            "meses_faltantes": dict(sorted(meses_faltantes.items())),
            "meses_na_base": {mes: meses_base[mes] for mes in meses},
            "ultima_competencia_base": max((it["data"] for _, it in itens_base
                                          if it["data"]), default="nenhuma"),
        })
    return origem


def main():
    p = argparse.ArgumentParser(description="Conferencia privada das pendencias da BASE_DADOS_GERAL.")
    p.add_argument("--pasta", type=Path, default=PASTA)
    p.add_argument("--auditor", type=Path, default=AUDITOR)
    a = p.parse_args()
    try:
        grupos = analisar(a.pasta, carregar(a.auditor))
        print("\n=== CONTROLADORIA HAIZE V7.6 - CONFERENCIA DE CONSOLIDACAO ===")
        for g in grupos:
            print("\n%s: %s lancamentos fora da base geral" % (g["condominio"], g["quantidade"]))
            print("  Ultima competencia na base geral: %s" % g["ultima_competencia_base"])
            for mes, num in g["meses_faltantes"].items():
                print("  Competencia %s: %d fora da base | %d ja na base" %
                      (mes, num, g["meses_na_base"].get(mes, 0)))
            for tipo, num in sorted(g["classificacoes"].items()):
                print("  %s: %d" % (tipo, num))
        print("\nTOTAL fora da base: %d" % sum(g["quantidade"] for g in grupos))
        print("Correspondencias por data, valor e texto nao comprovam duplicidade.")
        print("SOMENTE LEITURA. Nenhuma planilha modificada ou informacao enviada a internet.")
    except Exception as erro:
        print("ERRO: %s: %s" % (type(erro).__name__, erro), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
