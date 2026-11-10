# -*- coding: utf-8 -*-
"""Diagnostico local de lancamentos classificados fora da base geral (V7.6).

Somente leitura. Nenhuma escrita em XLSM ou CSV, macro ou acesso a rede.
Usa exclusivamente o auditor ja baixado de nosso repositorio.
Exibe apenas totais agregados por condominio e competencia.
"""
import argparse
from collections import Counter
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys

PASTA_PADRAO = Path(r"C:\Users\Windows\Music\Sistema_Rateio\CONDOMÍNIOS")
AUDITOR_PADRAO = Path.home() / "Downloads" / "auditar_planilhas_haize_v76.py"


def carregar_auditor(caminho):
    if not caminho.is_file():
        raise FileNotFoundError(f"Auditor original nao encontrado: {caminho}")
    spec = importlib.util.spec_from_file_location("auditor_custos_haize_v76", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def analisar(pasta, auditor):
    if not pasta.is_dir():
        raise FileNotFoundError(f"Pasta das planilhas nao encontrada: {pasta}")
    base_path = pasta / "BASE_DADOS_GERAL.xlsm"
    mapeamento, base, _, duplicados_base = auditor.extrair_base(base_path)
    if duplicados_base:
        raise ValueError("Base geral com IDs duplicados: revisar auditoria completa.")
    if len(mapeamento) != 10:
        raise ValueError(f"Esperava 10 condominios, encontrei {len(mapeamento)}. Revisar auditoria.")
    resultado = []
    for nome, arquivo in mapeamento:
        caminho = pasta / arquivo
        if not caminho.is_file():
            raise FileNotFoundError(f"Planilha de condominio ausente: {arquivo}")
        planilha = auditor.extrair_condominio(caminho, nome)
        ids_base = {uid for uid, item in base.items()
                    if auditor.canon(item["condominio"]) == auditor.canon(nome)}
        pendentes = [item for uid, item in planilha["classificadas"].items()
                     if uid not in ids_base]
        if not pendentes:
            continue
        datas = [date.fromisoformat(item["data"]) for item in pendentes]
        meses = Counter(dt.strftime("%Y-%m") for dt in datas)
        resultado.append({
            "condominio": nome,
            "quantidade": len(pendentes),
            "valor": sum((item["valor"] for item in pendentes), Decimal("0.00")),
            "mais_antigo": min(datas),
            "mais_recente": max(datas),
            "meses": dict(sorted(meses.items())),
        })
    return resultado


def main():
    ap = argparse.ArgumentParser(description="Resumo privado de pendencias da base geral, sem enviar dados.")
    ap.add_argument("--pasta", type=Path, default=PASTA_PADRAO)
    ap.add_argument("--auditor", type=Path, default=AUDITOR_PADRAO)
    args = ap.parse_args()
    try:
        auditor = carregar_auditor(args.auditor)
        grupos = analisar(args.pasta, auditor)
        total = sum(x["quantidade"] for x in grupos)
        soma = sum((x["valor"] for x in grupos), Decimal("0.00"))
        print("\n=== DIAGNOSTICO V7.6 - LANCAMENTOS NAO CONSOLIDADOS ===")
        for grupo in grupos:
            meses = ", ".join(f"{mes}: {qtd}" for mes, qtd in grupo["meses"].items())
            print(f"\n{grupo['condominio']}: {grupo['quantidade']} lancamentos")
            print(f"  Valor total pendente: {auditor.br(grupo['valor'])}")
            print(f"  Periodo das competencias: {grupo['mais_antigo']} ate {grupo['mais_recente']}")
            print(f"  Por mes: {meses}")
        print(f"\nTOTAL: {total} pendentes | valor: {auditor.br(soma)}")
        if total != 19:
            print("AVISO: o total difere dos 19 identificados na auditoria anterior. "
                  "Verifique se as planilhas foram atualizadas.")
        print("\nSOMENTE LEITURA. Nenhuma planilha alterada. Nenhum dado enviado a internet.")
    except Exception as erro:
        print(f"ERRO: {type(erro).__name__}: {erro}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
