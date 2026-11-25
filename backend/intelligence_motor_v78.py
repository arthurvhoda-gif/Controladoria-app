# -*- coding: utf-8 -*-
"""HAIZE INTELLIGENCE V7.8 — núcleo privado de análise histórica (somente leitura).

Não acessa banco, rede, e-mail ou endpoints HTTP. Recebe exclusivamente
LancamentoValidado da V7.7, com fonte histórica explícita. Não interpreta
valores negativos como economia, reembolso ou estorno sem evidência.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from custos_importacao_v77 import LancamentoValidado, ORIGEM


LIMITE_LANCAMENTOS = 50_000
AUMENTO_MINIMO_CENTAVOS = 30_000  # R$ 300: triagem, não irregularidade
AUMENTO_MINIMO_PERCENTUAL = 35   # comparação com mediana de três meses


class ErroAnalisePrivada(ValueError):
    """Rejeição sem expor dados particulares."""


@dataclass(frozen=True)
class ResumoMensal:
    condominio_id: int
    competencia: str
    lancamentos: int
    despesas_positivas_centavos: int
    ajustes_negativos_centavos: int
    saldo_centavos: int


@dataclass(frozen=True)
class ResumoCategoria:
    condominio_id: int
    categoria_chave: str
    lancamentos: int
    despesas_positivas_centavos: int
    ajustes_negativos_centavos: int
    saldo_centavos: int


@dataclass(frozen=True)
class AlertaRevisao:
    condominio_id: int
    categoria_chave: str
    competencia: str
    valor_atual_centavos: int
    referencia_mediana_centavos: int
    aumento_centavos: int
    aumento_percentual_inteiro: int
    classificacao: str = "aumento_para_revisao"


@dataclass(frozen=True)
class ResultadoIntelligence:
    fonte: str
    lancamentos: int
    condominios: int
    competencias_observadas: int
    despesas_positivas_centavos: int
    ajustes_negativos_centavos: int
    saldo_centavos: int
    meses: tuple[ResumoMensal, ...]
    categorias: tuple[ResumoCategoria, ...]
    alertas: tuple[AlertaRevisao, ...]
    ressalvas: tuple[str, ...]


def _anterior(mes: date) -> date:
    if mes.month == 1:
        return date(mes.year - 1, 12, 1)
    return date(mes.year, mes.month - 1, 1)


def _validar_entrada(lancamentos):
    if not isinstance(lancamentos, (tuple, list)) or not (
        1 <= len(lancamentos) <= LIMITE_LANCAMENTOS
    ):
        raise ErroAnalisePrivada("análise: lote vazio, inválido ou grande demais")
    chaves = set()
    for item in lancamentos:
        if not isinstance(item, LancamentoValidado) or item.origem != ORIGEM:
            raise ErroAnalisePrivada("análise: fonte não validada ou misturada")
        if (
            isinstance(item.condominio_id, bool)
            or not isinstance(item.condominio_id, int)
            or item.condominio_id <= 0
            or not isinstance(item.valor_centavos, int)
            or isinstance(item.valor_centavos, bool)
            or not isinstance(item.competencia, date)
            or item.competencia.day != 1
        ):
            raise ErroAnalisePrivada("análise: registro inconsistente")
        if item.chave in chaves:
            raise ErroAnalisePrivada("análise: identificador duplicado na fonte")
        chaves.add(item.chave)


def analisar_historico_privado(lancamentos):
    """Analisa despesas V7.7 validadas, sem produzir efeitos externos.

    Alertas exigem quatro meses *consecutivos* com despesas positivas na
    mesma categoria/condomínio. Compara o mês atual à mediana dos 3
    anteriores, desde que a diferença seja >= R$ 300 e >= 35%.
    Um alerta só recomenda revisão; não afirma fraude, economia ou erro.
    """
    _validar_entrada(lancamentos)
    por_mes = defaultdict(lambda: [0, 0, 0])
    por_categoria = defaultdict(lambda: [0, 0, 0])
    serie_categoria_mes = defaultdict(int)
    condominios = set()
    competencias = set()
    total_positivo = total_negativo = 0

    for item in lancamentos:
        mes = item.competencia
        condominios.add(item.condominio_id)
        competencias.add(mes)
        ch_mes = (item.condominio_id, mes)
        ch_cat = (item.condominio_id, item.categoria_chave)
        positivo = max(item.valor_centavos, 0)
        negativo = -min(item.valor_centavos, 0)
        total_positivo += positivo
        total_negativo += negativo

        for chave, destino in ((ch_mes, por_mes), (ch_cat, por_categoria)):
            resumo = destino[chave]
            resumo[0] += 1
            resumo[1] += positivo
            resumo[2] += negativo

        serie_categoria_mes[(item.condominio_id, item.categoria_chave, mes)] += positivo

    meses = tuple(
        ResumoMensal(cid, mes.isoformat(), qtd, positivo, negativo, positivo - negativo)
        for (cid, mes), (qtd, positivo, negativo) in sorted(por_mes.items())
    )
    categorias = tuple(
        ResumoCategoria(cid, categoria, qtd, positivo, negativo, positivo - negativo)
        for (cid, categoria), (qtd, positivo, negativo) in sorted(por_categoria.items())
    )

    alertas = []
    for (cid, categoria, mes), atual in sorted(serie_categoria_mes.items()):
        if atual <= 0:
            continue
        anteriores = []
        cursor = mes
        for _ in range(3):
            cursor = _anterior(cursor)
            valor = serie_categoria_mes.get((cid, categoria, cursor), 0)
            if valor <= 0:
                break  # mês ausente não significa zero; sem base confiável
            anteriores.append(valor)
        if len(anteriores) != 3:
            continue

        referencia = sorted(anteriores)[1]  # mediana inteira, sem float
        aumento = atual - referencia
        if (
            aumento >= AUMENTO_MINIMO_CENTAVOS
            and aumento * 100 >= referencia * AUMENTO_MINIMO_PERCENTUAL
        ):
            alertas.append(AlertaRevisao(
                condominio_id=cid,
                categoria_chave=categoria,
                competencia=mes.isoformat(),
                valor_atual_centavos=atual,
                referencia_mediana_centavos=referencia,
                aumento_centavos=aumento,
                aumento_percentual_inteiro=(aumento * 100) // referencia,
            ))

    return ResultadoIntelligence(
        fonte=ORIGEM,
        lancamentos=len(lancamentos),
        condominios=len(condominios),
        competencias_observadas=len(competencias),
        despesas_positivas_centavos=total_positivo,
        ajustes_negativos_centavos=total_negativo,
        saldo_centavos=total_positivo - total_negativo,
        meses=meses,
        categorias=categorias,
        alertas=tuple(alertas),
        ressalvas=(
            "Dados apenas da fonte historica V7.7; nao somar automaticamente com financeiro ou solicitacoes.",
            "Valores negativos sao ajustes nao classificados; nao representam economia confirmada.",
            "Meses ausentes nao sao tratados como despesa zero.",
            "Alertas sao sinais estatisticos simples para revisao humana, nao conclusoes de irregularidade.",
        ),
    )
