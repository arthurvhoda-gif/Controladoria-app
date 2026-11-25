
# -*- coding: utf-8 -*-
"""HAIZE INTELLIGENCE - Oportunidades de reducao de custos."""

from dataclasses import dataclass
from collections import defaultdict

from intelligence_motor_v78 import analisar_historico_privado

from intelligence_previsao_v78 import (
    interpretar_mes,
    deslocar_mes,
)


class ErroOportunidades(ValueError):
    """Dados insuficientes ou invalidos."""


@dataclass(frozen=True)
class OportunidadeEconomia:

    condominio_id: int
    categoria: str
    referencia_mensal_centavos: int
    total_recente_centavos: int
    impacto_adicional_centavos: int
    meses_com_aumento: int
    prioridade: str
    recomendacao: str


@dataclass(frozen=True)
class ResultadoOportunidades:

    condominio_id: int
    categorias_avaliadas: int
    categorias_sem_base: int
    oportunidades: tuple


def identificar_oportunidades_v78(
    registros,
    condominio_id,
    ultimo_mes_fechado,
    meses_fechados,
):
    """
    Compara tres meses recentes com a mediana
    dos tres meses anteriores.

    Identifica aumentos persistentes.

    Nao afirma economia comprovada.
    Nao modifica dados ou contratos.
    """

    if (
        isinstance(condominio_id, bool)
        or not isinstance(condominio_id, int)
        or condominio_id <= 0
    ):
        raise ErroOportunidades(
            "Condominio invalido."
        )

    referencia = interpretar_mes(
        ultimo_mes_fechado
    )

    if not isinstance(
        meses_fechados,
        (list, tuple, set, frozenset),
    ):
        raise ErroOportunidades(
            "Informe as competencias fechadas."
        )

    fechados = {
        interpretar_mes(m)
        for m in meses_fechados
    }

    meses = [
        deslocar_mes(referencia, i)
        for i in range(-5, 1)
    ]

    if not set(meses).issubset(fechados):
        raise ErroOportunidades(
            "Sao necessarios seis meses fechados."
        )

    # Valida a integridade do conjunto recebido.
    analisar_historico_privado(registros)

    series = defaultdict(
        lambda: defaultdict(int)
    )

    for registro in registros:

        if (
            registro.condominio_id != condominio_id
            or registro.competencia not in meses
        ):
            continue

        series[registro.categoria_chave][
            registro.competencia
        ] += max(registro.valor_centavos, 0)

    avaliadas = 0
    sem_base = 0
    oportunidades = []

    for categoria, valores in series.items():

        if any(
            valores.get(mes, 0) <= 0
            for mes in meses
        ):
            sem_base += 1
            continue

        avaliadas += 1

        anteriores = [
            valores[mes]
            for mes in meses[:3]
        ]

        recentes = [
            valores[mes]
            for mes in meses[3:]
        ]

        base = sorted(anteriores)[1]

        aumentos = sum(
            1 for atual in recentes
            if atual - base >= 10000
            and (atual - base) * 100 >= base * 15
        )

        # Exige persistencia em pelo menos
        # dois dos tres meses recentes.
        if aumentos < 2:
            continue

        impacto = sum(recentes) - base * 3

        if impacto <= 0:
            continue

        prioridade = (
            "ALTA"
            if impacto >= 100000
            else "MODERADA"
        )

        oportunidades.append(
            OportunidadeEconomia(
                condominio_id=condominio_id,
                categoria=categoria,
                referencia_mensal_centavos=base,
                total_recente_centavos=sum(recentes),
                impacto_adicional_centavos=impacto,
                meses_com_aumento=aumentos,
                prioridade=prioridade,
                recomendacao=(
                    "Revisar contratos, precos unitarios, "
                    "quantidades, frequencia e necessidade "
                    "das despesas. Verificar causas antes "
                    "de estimar economia recuperavel."
                ),
            )
        )

    oportunidades.sort(
        key=lambda item: (
            -item.impacto_adicional_centavos,
            item.categoria,
        )
    )

    return ResultadoOportunidades(
        condominio_id=condominio_id,
        categorias_avaliadas=avaliadas,
        categorias_sem_base=sem_base,
        oportunidades=tuple(oportunidades),
    )
