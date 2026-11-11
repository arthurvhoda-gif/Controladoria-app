# -*- coding: utf-8 -*-
"""V7.7: validação e prévia pura de despesas históricas; ZERO gravações.

Aceita dicionários com chaves do auditor V7.6 (id, condominio, descricao,
data, valor, categoria) e mapa EXPLÍCITO nome->ID validado pelo operador.
Não importa planilhas reais, não faz conexão HTTP e não importa a API.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import unicodedata
from typing import Mapping

ORIGEM = "base_geral_xlsm"
_LIMITE_REGISTROS = 50000
_MAX_CENTAVOS = 9_000_000_000_000_000
_CATEGORIAS_INVALIDAS = {"nao classificado", "nao classificados"}
_FORM_VALOR = re.compile(r"-?\d+(?:\.\d{1,2})?\Z")
_FORM_DATA = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class ErroValidacaoCustos(ValueError):
    """Erro sem expor descrições ou valores particulares."""


def chave_nome(nome):
    if not isinstance(nome, str):
        return ""
    norm = unicodedata.normalize("NFKD", nome)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return " ".join(norm.casefold().split())


def _texto(valor, campo, limite):
    if not isinstance(valor, str):
        raise ErroValidacaoCustos(f"{campo}: precisa ser texto")
    saida = unicodedata.normalize("NFC", valor).strip()
    if not saida or len(saida) > limite or any(ord(c) < 32 for c in saida):
        raise ErroValidacaoCustos(f"{campo}: vazio, longo demais ou com caracteres inválidos")
    return saida


def _centavos(valor):
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ErroValidacaoCustos("valor: use Decimal ou texto, nunca float")
    if isinstance(valor, Decimal):
        dec = valor
    elif isinstance(valor, int):
        dec = Decimal(valor)
    elif isinstance(valor, str) and _FORM_VALOR.fullmatch(valor):
        try:
            dec = Decimal(valor)
        except InvalidOperation as exc:
            raise ErroValidacaoCustos("valor: inválido") from exc
    else:
        raise ErroValidacaoCustos("valor: formato decimal inválido")
    if not dec.is_finite() or dec != dec.quantize(Decimal("0.01")):
        raise ErroValidacaoCustos("valor: precisão inválida (máximo 2 casas)")
    convertido = int(dec * 100)
    if abs(convertido) > _MAX_CENTAVOS:
        raise ErroValidacaoCustos("valor: fora do limite")
    return convertido


def _data(valor):
    if isinstance(valor, datetime):
        raise ErroValidacaoCustos("data: envie apenas a data, sem horário")
    if isinstance(valor, date):
        d = valor
    elif isinstance(valor, str) and _FORM_DATA.fullmatch(valor):
        try:
            d = date.fromisoformat(valor)
        except ValueError as exc:
            raise ErroValidacaoCustos("data: inválida") from exc
    else:
        raise ErroValidacaoCustos("data: use AAAA-MM-DD")
    if not 2000 <= d.year <= 2100:
        raise ErroValidacaoCustos("data: fora do intervalo permitido")
    return d


@dataclass(frozen=True)
class LancamentoValidado:
    condominio_id: int
    origem: str
    id_origem: str
    data_original: date
    competencia: date
    descricao: str
    categoria_original: str
    categoria_chave: str
    valor_centavos: int
    hash_conteudo: str

    @property
    def chave(self):
        return (self.condominio_id, self.origem, self.id_origem)


def validar_lancamento(raw, mapa_ids):
    if not isinstance(raw, Mapping):
        raise ErroValidacaoCustos("registro: formato inválido")
    nome = _texto(raw.get("condominio"), "condominio", 180)
    key_nome = chave_nome(nome)
    if key_nome not in mapa_ids:
        raise ErroValidacaoCustos("condominio: sem vínculo aprovado no cadastro")
    condominio_id = mapa_ids[key_nome]
    uid = _texto(raw.get("id"), "id", 180)
    descricao = _texto(raw.get("descricao"), "descricao", 1000)
    categoria = _texto(raw.get("categoria"), "categoria", 180)
    categoria_key = chave_nome(categoria)
    if categoria_key in _CATEGORIAS_INVALIDAS:
        raise ErroValidacaoCustos("categoria: não classificada")
    data_original = _data(raw.get("data"))
    valor_centavos = _centavos(raw.get("valor"))
    competencia = data_original.replace(day=1)
    conteudo = {
        "condominio_id": condominio_id, "origem": ORIGEM,
        "id_origem": uid, "data_original": data_original.isoformat(),
        "descricao": descricao, "categoria_original": categoria,
        "valor_centavos": valor_centavos,
    }
    resumo = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(resumo.encode("utf-8")).hexdigest()
    return LancamentoValidado(
        condominio_id=condominio_id, origem=ORIGEM,
        id_origem=uid, data_original=data_original,
        competencia=competencia, descricao=descricao,
        categoria_original=categoria, categoria_chave=categoria_key,
        valor_centavos=valor_centavos, hash_conteudo=checksum,
    )


def validar_lote(registros, mapa_condominios):
    """Valida TUDO antes da prévia. Nunca aceita lote parcialmente válido."""
    if not isinstance(registros, (tuple, list)) or not 1 <= len(registros) <= _LIMITE_REGISTROS:
        raise ErroValidacaoCustos("lote: quantidade de registros inválida")
    if not isinstance(mapa_condominios, Mapping) or not mapa_condominios:
        raise ErroValidacaoCustos("condominios: forneça mapa explícito nome->ID")
    ids = {}
    id_para_nome = {}
    for nome, cid in mapa_condominios.items():
        nome_chave = chave_nome(nome)
        if not nome_chave or isinstance(cid, bool) or not isinstance(cid, int) or cid <= 0:
            raise ErroValidacaoCustos("condominios: associação inválida")
        if nome_chave in ids or (cid in id_para_nome and id_para_nome[cid] != nome_chave):
            raise ErroValidacaoCustos("condominios: nomes ou IDs repetidos")
        ids[nome_chave] = cid
        id_para_nome[cid] = nome_chave
    validados = []
    chaves_vistas = set()
    for i, raw in enumerate(registros, 1):
        try:
            reg = validar_lancamento(raw, ids)
            if reg.chave in chaves_vistas:
                raise ErroValidacaoCustos("identificador de origem repetido no condomínio")
            chaves_vistas.add(reg.chave)
            validados.append(reg)
        except ErroValidacaoCustos as exc:
            raise ErroValidacaoCustos(f"linha {i}: {exc}") from exc
    return tuple(validados)


@dataclass(frozen=True)
class PreviaImportacao:
    novos: int
    alterados: int
    inalterados: int
    ausentes_na_origem: int
    total_centavos: int
    registros: int
    # Apenas contagens: sem descrições, IDs ou dados financeiros individuais.
    revisao_manual_obrigatoria: bool = True


def montar_previa(validados, existentes, *, cobertura_completa=False):
    """Sem side effects. Ausentes NUNCA são excluídos automaticamente.

    'cobertura_completa' é uma declaração explícita do operador;
    se False, não se inferem ausências a partir de um lote parcial.
    """
    if not isinstance(validados, (tuple, list)) or not all(
        isinstance(v, LancamentoValidado) for v in validados
    ):
        raise ErroValidacaoCustos("prévia: lote não validado")
    if not isinstance(existentes, Mapping):
        raise ErroValidacaoCustos("prévia: estado atual inválido")
    chaves = [r.chave for r in validados]
    if len(chaves) != len(set(chaves)):
        raise ErroValidacaoCustos("prévia: identificadores duplicados")
    novos = alterados = inalterados = 0
    for item in validados:
        anterior = existentes.get(item.chave)
        if anterior is None:
            novos += 1
        elif not isinstance(anterior, LancamentoValidado):
            raise ErroValidacaoCustos("prévia: registro anterior inválido")
        elif anterior.hash_conteudo == item.hash_conteudo:
            inalterados += 1
        else:
            alterados += 1
    faltantes = 0
    if cobertura_completa:
        abrangidos = {(r.condominio_id, r.origem) for r in validados}
        faltantes = sum(
            1 for chave in existentes
            if (chave[0], chave[1]) in abrangidos and chave not in set(chaves)
        )
    return PreviaImportacao(
        novos=novos, alterados=alterados, inalterados=inalterados,
        ausentes_na_origem=faltantes,
        total_centavos=sum(r.valor_centavos for r in validados),
        registros=len(validados),
    )
