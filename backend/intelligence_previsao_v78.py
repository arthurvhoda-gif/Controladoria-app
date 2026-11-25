
# -*- coding: utf-8 -*-
"""HAIZE INTELLIGENCE - Previsao financeira privada."""

from dataclasses import dataclass
from datetime import date
import re

from intelligence_motor_v78 import analisar_historico_privado


class ErroPrevisao(ValueError):
    """Historico insuficiente ou inconsistente."""


@dataclass(frozen=True)
class PrevisaoFinanceira:
    condominio_id: int
    competencia_prevista: str
    metodo: str
    meses_analisados: int
    previsao_centavos: int
    erro_medio_centavos: int
    erro_maximo_centavos: int
    cenario_inferior_centavos: int
    cenario_superior_centavos: int


def interpretar_mes(valor):

    if (
        not isinstance(valor, str)
        or not re.fullmatch(
            r"20\d{2}-(0[1-9]|1[0-2])",
            valor,
        )
    ):
        raise ErroPrevisao("Competencia invalida.")

    return date.fromisoformat(valor + "-01")


def deslocar_mes(mes, deslocamento):

    indice = mes.year * 12 + mes.month - 1
    ano, numero = divmod(indice + deslocamento, 12)

    return date(ano, numero + 1, 1)


def mediana_tres(valores):

    return sorted(valores[-3:])[1]


def ultimo_mes(valores):

    return valores[-1]


def prever_despesas_v78(
    registros,
    condominio_id,
    ultimo_mes_fechado,
    meses_fechados,
):
    """
    Previsao de despesas positivas para o proximo mes.

    Requer seis competencias consecutivas com
    fechamento confirmado e registros positivos.

    Compara dois metodos por validacao retrospectiva.

    Nao acessa banco, rede ou servicos externos.
    """

    if (
        isinstance(condominio_id, bool)
        or not isinstance(condominio_id, int)
        or condominio_id <= 0
    ):
        raise ErroPrevisao("Condominio invalido.")

    referencia = interpretar_mes(ultimo_mes_fechado)

    if not isinstance(
        meses_fechados,
        (tuple, list, set, frozenset),
    ):
        raise ErroPrevisao(
            "Informe os meses com fechamento confirmado."
        )

    fechados = {
        interpretar_mes(mes)
        for mes in meses_fechados
    }

    meses = [
        deslocar_mes(referencia, i)
        for i in range(-5, 1)
    ]

    if not set(meses).issubset(fechados):
        raise ErroPrevisao(
            "Sao necessarios seis meses consecutivos fechados."
        )

    historico = analisar_historico_privado(registros)

    totais = {
        date.fromisoformat(r.competencia):
            r.despesas_positivas_centavos
        for r in historico.meses
        if r.condominio_id == condominio_id
    }

    if any(
        totais.get(mes, 0) <= 0
        for mes in meses
    ):
        raise ErroPrevisao(
            "Historico insuficiente para uma previsao."
        )

    valores = [
        totais[mes]
        for mes in meses
    ]

    metodos = [
        ("ultimo_mes", ultimo_mes),
        ("mediana_3_meses", mediana_tres),
    ]

    resultados = []

    for nome, metodo in metodos:

        erros = []

        # Simula previsoes utilizando somente
        # informacoes anteriores ao mes previsto.

        for indice in range(3, len(valores)):

            anteriores = valores[:indice]

            estimativa = metodo(anteriores)

            realizado = valores[indice]

            erros.append(
                abs(realizado - estimativa)
            )

        resultados.append({
            "nome": nome,
            "metodo": metodo,
            "erro_total": sum(erros),
            "erro_medio": (
                sum(erros) + len(erros) - 1
            ) // len(erros),
            "erro_maximo": max(erros),
        })

    melhor = min(
        resultados,
        key=lambda item: item["erro_total"],
    )

    previsao = melhor["metodo"](valores)

    margem = melhor["erro_maximo"]

    proximo_mes = deslocar_mes(
        referencia,
        1,
    )

    return PrevisaoFinanceira(
        condominio_id=condominio_id,
        competencia_prevista=proximo_mes.strftime(
            "%Y-%m"
        ),
        metodo=melhor["nome"],
        meses_analisados=len(valores),
        previsao_centavos=previsao,
        erro_medio_centavos=melhor["erro_medio"],
        erro_maximo_centavos=margem,
        cenario_inferior_centavos=max(
            0,
            previsao - margem,
        ),
        cenario_superior_centavos=(
            previsao + margem
        ),
    )
