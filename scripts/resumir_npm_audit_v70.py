#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resumo do npm audit para CI, sem URLs de pacotes ou dumps extensos.

O job de auditoria deve reportar vulnerabilidades sem mascarar erros
de rede/JSON. Não faz atualizações automáticas nem desliga funcionalidades.
"""
import json
from pathlib import Path
import sys

PESOS = ("critical", "high", "moderate", "low")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python scripts/resumir_npm_audit_v70.py <arquivo-json>")
    arquivo = Path(sys.argv[1])
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if "error" in dados or "vulnerabilities" not in dados or "metadata" not in dados:
        raise SystemExit("Falha ao obter auditoria npm; não confundir erro com ausência de vulnerabilidades.")
    totais = dados["metadata"]["vulnerabilities"]
    vuln = dados["vulnerabilities"]
    print("AUDITORIA NPM — inventário, não conformidade de segurança:")
    print("Severidades: " + ", ".join(f"{s}={totais.get(s, 0)}" for s in PESOS))
    for nome, info in sorted(vuln.items()):
        gravidade = info.get("severity", "unknown")
        fix = info.get("fixAvailable")
        tipo = ("atualização compatível" if fix is True
                else "revisar troca/versão" if fix is False
                else "possível mudança de versão principal")
        if gravidade in PESOS:
            print(f"  - {nome}: {gravidade} / {tipo}")
    risco_alto = sum(int(totais.get(s, 0)) for s in ("high", "critical"))
    if risco_alto:
        print(f"::warning::Existem {risco_alto} vulnerabilidades altas/críticas a tratar antes de produção.")
    else:
        print("Sem vulnerabilidades altas/críticas no escopo auditado.")


if __name__ == "__main__":
    main()
