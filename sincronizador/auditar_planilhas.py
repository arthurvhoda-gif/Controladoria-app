# -*- coding: utf-8 -*-
"""Auditoria local, SOMENTE LEITURA, das planilhas XLSM da Controladoria Haize.

Não altera planilhas, não executa macros, não chama API nem acessa o Neon.
Usa somente a biblioteca padrão do Python (3.10+).
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path, PureWindowsPath
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

PASTA_PADRAO = Path(r"C:\Users\Windows\Music\Sistema_Rateio\CONDOMÍNIOS")
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P = "{http://schemas.openxmlformats.org/package/2006/relationships}"
COLUNA_REGEX = re.compile(r"^[A-Z]+")


def canon(texto):
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


def texto(valor):
    return str(valor or "").strip()


def dinheiro(valor):
    if valor is None or str(valor).strip() == "":
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def br(valor):
    if valor is None:
        return "-"
    s = f"{valor:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def data_excel(valor):
    if valor is None or str(valor).strip() == "":
        return ""
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(valor))).date().isoformat()
    except (ValueError, OverflowError, TypeError):
        return texto(valor)


class LeitorXlsm:
    """Leitura OOXML usando apenas zipfile/XML, sem macros e sem modificar arquivos."""

    def __init__(self, arquivo):
        self.arquivo = arquivo
        self.zip = ZipFile(arquivo, "r")
        wb = ET.fromstring(self.zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels"))
        mapa_rel = {r.attrib["Id"]: r.attrib.get("Target", "") for r in rels}
        self.abas = {}
        for sh in wb.findall(f"{M}sheets/{M}sheet"):
            destino = mapa_rel[sh.attrib[R + "id"]].replace("\\", "/")
            if destino.startswith("/"):
                destino = destino.lstrip("/")
            elif not destino.startswith("xl/"):
                destino = "xl/" + destino
            self.abas[sh.attrib["name"]] = destino
        self.strings = []
        if "xl/sharedStrings.xml" in self.zip.namelist():
            raiz = ET.fromstring(self.zip.read("xl/sharedStrings.xml"))
            for si in raiz.findall(f"{M}si"):
                self.strings.append("".join(t.text or "" for t in si.iter(f"{M}t")))

    def linhas(self, aba, colunas=None):
        if aba not in self.abas:
            raise ValueError(f"Aba obrigatória ausente: {aba}")
        with self.zip.open(self.abas[aba]) as f:
            eventos = ET.iterparse(f, events=("start", "end"))
            _, raiz = next(eventos)
            for evento, el in eventos:
                if evento != "end" or el.tag != f"{M}row":
                    continue
                row_num = int(el.attrib.get("r", 0))
                dados = {}
                for celula in el.findall(f"{M}c"):
                    ref = celula.attrib.get("r", "")
                    match = COLUNA_REGEX.match(ref)
                    if not match:
                        continue
                    coluna = match.group(0)
                    if colunas is not None and coluna not in colunas:
                        continue
                    tipo = celula.attrib.get("t")
                    v = celula.find(f"{M}v")
                    bruto = v.text if v is not None else None
                    if tipo == "s" and bruto is not None:
                        bruto = self.strings[int(bruto)]
                    elif tipo == "inlineStr":
                        bruto = "".join(t.text or "" for t in celula.iter(f"{M}t"))
                    # Cells with formulas are read only from cached values (not recalculated).
                    if bruto is not None:
                        dados[coluna] = bruto
                if dados:
                    yield row_num, dados
                el.clear()
                raiz.clear()

    def fechar(self):
        self.zip.close()


def extrair_base(arquivo):
    leitor = LeitorXlsm(arquivo)
    try:
        mapeamento = []
        for linha, d in leitor.linhas("CONDOMINIOS", {"A", "B"}):
            if linha == 1 or not texto(d.get("A")) or not texto(d.get("B")):
                continue
            nome = texto(d["A"])
            # Some references are complete Windows paths, but only the filename is used.
            nome_arquivo = PureWindowsPath(texto(d["B"])).name
            if not nome_arquivo.lower().endswith(".xlsm"):
                raise ValueError(f"Arquivo não XLSM no cadastro de condomínios: {nome_arquivo}")
            mapeamento.append((nome, nome_arquivo))
        lancamentos = {}
        duplicados = []
        for linha, d in leitor.linhas("BASE_GERAL", {"A", "B", "C", "D", "K", "L"}):
            if linha == 1:
                continue
            uid = texto(d.get("L"))
            if not uid or not texto(d.get("K")):
                continue
            item = {"id": uid, "descricao": texto(d.get("A")),
                    "data": data_excel(d.get("B")), "valor": dinheiro(d.get("C")),
                    "categoria": texto(d.get("D")), "condominio": texto(d.get("K"))}
            if uid in lancamentos:
                duplicados.append((uid, linha))
            lancamentos[uid] = item
        prazos = {}
        for linha, d in leitor.linhas("BASE_PRAZOS", {"A", "B", "C", "D", "E"}):
            if linha == 1 or not texto(d.get("A")) or not texto(d.get("B")):
                continue
            chave = (canon(d.get("A")), canon(d.get("B")))
            prazos[chave] = {"periodicidade": texto(d.get("C")),
                             "ultima": data_excel(d.get("D")),
                             "proxima": data_excel(d.get("E"))}
        return mapeamento, lancamentos, prazos, duplicados
    finally:
        leitor.fechar()


def extrair_condominio(arquivo, nome):
    leitor = LeitorXlsm(arquivo)
    try:
        resultado = {"nome": nome, "arquivo": arquivo.name, "despesas": 0,
                     "classificadas": {}, "total_classificado": Decimal("0.00"),
                     "pendentes": 0, "sem_id": [], "duplicados": [],
                     "datas_invalidas": [], "valores_invalidos": [], "manutencoes": {}}
        ids = set()
        for linha, d in leitor.linhas("GASTOS", {"A", "B", "C", "D", "L"}):
            if linha == 1:
                continue
            descricao = texto(d.get("A"))
            if not descricao:
                continue
            # Não contar linhas formatadas ou linhas de fórmulas auxiliares sem despesa.
            if not any(d.get(k) is not None for k in ("B", "C", "D")):
                continue
            resultado["despesas"] += 1
            categoria = texto(d.get("D"))
            if not categoria or canon(categoria) == "nao classificado":
                resultado["pendentes"] += 1
                continue
            uid = texto(d.get("L"))
            if not uid:
                resultado["sem_id"].append(linha)
                continue
            if uid in ids:
                resultado["duplicados"].append((linha, uid))
                continue
            ids.add(uid)
            valor = dinheiro(d.get("C"))
            if valor is None:
                resultado["valores_invalidos"].append(linha)
                continue
            dt = data_excel(d.get("B"))
            if not dt or not re.match(r"^\d{4}-\d{2}-\d{2}$", dt):
                resultado["datas_invalidas"].append(linha)
                continue
            item = {"id": uid, "descricao": descricao, "data": dt,
                    "valor": valor, "categoria": categoria, "condominio": nome}
            resultado["classificadas"][uid] = item
            resultado["total_classificado"] += valor
        if "PRAZOS" in leitor.abas:
            for linha, d in leitor.linhas("PRAZOS", {"A", "B", "C", "D"}):
                if linha == 1 or not texto(d.get("A")):
                    continue
                cat = canon(d.get("A"))
                resultado["manutencoes"][cat] = {
                    "nome": texto(d.get("A")),
                    "periodicidade": texto(d.get("B")),
                    "ultima": data_excel(d.get("C")),
                    "proxima": data_excel(d.get("D")),
                }
        return resultado
    finally:
        leitor.fechar()


def registrar(detalhes, tipo, condominio, id_registro, mensagem):
    detalhes.append({"tipo": tipo, "condominio": condominio,
                     "id_registro": id_registro, "detalhe": mensagem})


def auditar(pasta, destino):
    base_path = pasta / "BASE_DADOS_GERAL.xlsm"
    if not base_path.is_file():
        raise FileNotFoundError(f"Base geral não encontrada: {base_path}")
    mapeamento, base, prazos_base, duplicados_base = extrair_base(base_path)
    if not mapeamento:
        raise ValueError("A aba CONDOMINIOS da base geral não lista arquivos de origem.")
    detalhes = []
    resumo = []
    for uid, linha in duplicados_base:
        registrar(detalhes, "ID_DUPLICADO_BASE", "BASE_GERAL", uid,
                 f"ID repetido na linha {linha} da BASE_GERAL")
    encontrados = set()
    for nome, arquivo_nome in mapeamento:
        caminho = pasta / arquivo_nome
        if not caminho.is_file():
            registrar(detalhes, "ARQUIVO_AUSENTE", nome, "", f"Não encontrei {arquivo_nome}")
            resumo.append({"condominio": nome, "arquivo": arquivo_nome,
                           "despesas": "-", "classificadas": "-", "nao_classificadas": "-",
                           "total_planilha": "-", "registros_na_base": "-", "total_base": "-",
                           "manutencoes": "-", "divergencias": "arquivo ausente"})
            continue
        try:
            c = extrair_condominio(caminho, nome)
        except (ValueError, BadZipFile, KeyError, ET.ParseError) as exc:
            registrar(detalhes, "ERRO_LEITURA", nome, "", str(exc))
            resumo.append({"condominio": nome, "arquivo": arquivo_nome,
                           "despesas": "-", "classificadas": "-", "nao_classificadas": "-",
                           "total_planilha": "-", "registros_na_base": "-", "total_base": "-",
                           "manutencoes": "-", "divergencias": "erro de leitura"})
            continue
        for linha in c["sem_id"]:
            registrar(detalhes, "SEM_ID", nome, "", f"GASTOS linha {linha}: classificado sem ID")
        for linha, uid in c["duplicados"]:
            registrar(detalhes, "ID_DUPLICADO_ORIGEM", nome, uid, f"GASTOS linha {linha}")
        for linha in c["valores_invalidos"]:
            registrar(detalhes, "VALOR_INVALIDO", nome, "", f"GASTOS linha {linha}")
        for linha in c["datas_invalidas"]:
            registrar(detalhes, "DATA_INVALIDA", nome, "", f"GASTOS linha {linha}")
        regs_base = {uid: it for uid, it in base.items() if canon(it["condominio"]) == canon(nome)}
        encontrados.update(regs_base.keys())
        avisos_antes = len(detalhes)
        for uid, a in c["classificadas"].items():
            b = regs_base.get(uid)
            if b is None:
                registrar(detalhes, "NAO_ENCONTRADO_NA_BASE", nome, uid,
                         "Despesa classificada ainda não está na base geral")
                continue
            diffs = []
            for chave in ("descricao", "categoria"):
                if canon(a[chave]) != canon(b[chave]):
                    diffs.append(f"{chave}: origem={a[chave]!r}, base={b[chave]!r}")
            for chave in ("data", "valor"):
                if a[chave] != b[chave]:
                    diffs.append(f"{chave}: origem={a[chave]!s}, base={b[chave]!s}")
            if diffs:
                registrar(detalhes, "DADOS_DIFERENTES", nome, uid, "; ".join(diffs))
        for uid in regs_base:
            if uid not in c["classificadas"]:
                registrar(detalhes, "SOMENTE_NA_BASE", nome, uid,
                         "Existe na base geral, mas não entre as despesas classificadas da origem")
        for cat, manut in c["manutencoes"].items():
            base_m = prazos_base.get((canon(nome), cat))
            if base_m is None:
                registrar(detalhes, "PRAZO_AUSENTE_NA_BASE", nome, cat,
                         "Manutenção ausente em BASE_PRAZOS")
            else:
                diffs = [f"{k}: origem={manut[k]!s}, base={base_m[k]!s}"
                         for k in ("periodicidade", "ultima", "proxima")
                         if manut[k] != base_m[k]]
                if diffs:
                    registrar(detalhes, "PRAZO_DIFERENTE", nome, cat, "; ".join(diffs))
        total_base = sum((v["valor"] for v in regs_base.values() if v["valor"] is not None), Decimal("0"))
        resumo.append({"condominio": nome, "arquivo": arquivo_nome,
                       "despesas": c["despesas"], "classificadas": len(c["classificadas"]),
                       "nao_classificadas": c["pendentes"],
                       "total_planilha": br(c["total_classificado"]),
                       "registros_na_base": len(regs_base), "total_base": br(total_base),
                       "manutencoes": len(c["manutencoes"]),
                       "divergencias": len(detalhes)-avisos_antes + len(c["sem_id"]) + len(c["duplicados"]) + len(c["valores_invalidos"]) + len(c["datas_invalidas"])})
    # Entradas de base que não correspondem a nenhum condomínio cadastrado
    nomes = {canon(nome) for nome, _ in mapeamento}
    for uid, item in base.items():
        if canon(item["condominio"]) not in nomes:
            registrar(detalhes, "CONDOMINIO_DESCONHECIDO", item["condominio"], uid,
                     "Condomínio do lançamento não encontrado na aba CONDOMINIOS")
    destino.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (destino / "resumo_por_condominio.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(resumo[0].keys()), delimiter=";")
        writer.writeheader(); writer.writerows(resumo)
    with (destino / "divergencias.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["tipo", "condominio", "id_registro", "detalhe"], delimiter=";")
        writer.writeheader(); writer.writerows(detalhes)
    arquivo_resultado = destino / "RESUMO_DA_AUDITORIA.txt"
    with arquivo_resultado.open("w", encoding="utf-8") as f:
        f.write("CONTROLADORIA HAIZE - AUDITORIA LOCAL DAS PLANILHAS\n")
        f.write("="*58 + "\n")
        f.write("Execução: " + timestamp + "\n")
        f.write("Pasta de origem: " + str(pasta) + "\n")
        f.write(f"Condomínios cadastrados: {len(mapeamento)}\n")
        f.write(f"Lançamentos na base geral: {len(base)}\n")
        f.write(f"Divergências / alertas encontrados: {len(detalhes)}\n\n")
        for item in resumo:
            f.write(f"{item['condominio']}\n")
            f.write(f"  Despesas: {item['despesas']} | Classificadas: {item['classificadas']}"
                    f" | Não classificadas: {item['nao_classificadas']}\n")
            f.write(f"  Total da origem: {item['total_planilha']} | Total na base: {item['total_base']}\n")
            f.write(f"  Divergências: {item['divergencias']}\n")
        f.write("\nSomente leitura: nenhum arquivo Excel foi alterado.\n")
        f.write("Nenhuma informação foi enviada pela internet.\n")
        f.write("Mensagens de detalhe em divergencias.csv\n")
    print("\n=== AUDITORIA DE CUSTOS - CONTROLADORIA HAIZE ===\n")
    print(f"Condomínios: {len(mapeamento)} | Registros na base: {len(base)}")
    for item in resumo:
        print(f"- {item['condominio']}: "
              f"{item['classificadas']} classificados | {item['total_planilha']} "
              f"| divergências: {item['divergencias']}")
    print(f"\nDivergências/alertas totais: {len(detalhes)}")
    print("\nArquivos da auditoria em:")
    print("  " + str(destino / 'RESUMO_DA_AUDITORIA.txt'))
    print("  " + str(destino / 'resumo_por_condominio.csv'))
    print("  " + str(destino / 'divergencias.csv'))
    print("\nNENHUMA planilha alterada. NENHUM dado enviado ao Neon ou à internet.")
    return resumo, detalhes


def main():
    p = argparse.ArgumentParser(description="Auditoria de custos local (somente leitura).")
    p.add_argument("--pasta", type=Path, default=PASTA_PADRAO)
    p.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent / "relatorios")
    args = p.parse_args()
    try:
        auditar(args.pasta, args.saida)
    except Exception as exc:
        print(f"\nERRO: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
