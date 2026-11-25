
# -*- coding: utf-8 -*-
"""HAIZE INTELLIGENCE V7.8 - Relatorios privados."""

from datetime import date
import re

from intelligence_motor_v78 import (
    analisar_historico_privado,
)


def moeda(centavos):
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{resto:02d}"


def gerar_relatorio_privado_v78(
    registros,
    competencia,
):
    """
    Gera um relatorio mensal em texto.

    Nao grava dados.
    Nao envia emails.
    Nao acessa a rede.
    """

    if (
        not isinstance(competencia, str)
        or not re.fullmatch(
            r"20\d{2}-(0[1-9]|1[0-2])",
            competencia,
        )
    ):
        raise ValueError("Competencia invalida.")

    mes = date.fromisoformat(
        competencia + "-01"
    )

    historico = analisar_historico_privado(
        registros
    )

    registros_mes = [
        r for r in registros
        if r.competencia == mes
    ]

    if not registros_mes:
        raise ValueError(
            "Competencia sem registros disponiveis."
        )

    mensal = analisar_historico_privado(
        registros_mes
    )

    alertas = [
        a for a in historico.alertas
        if a.competencia == mes.isoformat()
    ]

    alertas.sort(
        key=lambda a: a.aumento_centavos,
        reverse=True,
    )

    linhas = [
        "HAIZE INTELLIGENCE",
        "RELATORIO EXECUTIVO PRIVADO",
        f"Competencia: {competencia}",
        "",
        "1. RESUMO FINANCEIRO",
        "",
        f"Condominios com registros: {mensal.condominios}",
        f"Lancamentos: {mensal.lancamentos}",
        (
            "Despesas positivas: "
            + moeda(
                mensal.despesas_positivas_centavos
            )
        ),
        (
            "Ajustes negativos: "
            + moeda(
                mensal.ajustes_negativos_centavos
            )
        ),
        (
            "Saldo dos lancamentos: "
            + moeda(mensal.saldo_centavos)
        ),
        "",
        "2. DESPESAS POR CONDOMINIO",
        "",
    ]

    for resumo in sorted(
        mensal.meses,
        key=lambda r: r.despesas_positivas_centavos,
        reverse=True,
    ):
        linhas.append(
            f"Condominio ID {resumo.condominio_id}: "
            f"{moeda(resumo.despesas_positivas_centavos)} "
            f"| {resumo.lancamentos} lancamentos"
        )

    linhas.extend([
        "",
        "3. CATEGORIAS PRIORITARIAS",
        "",
    ])

    categorias = sorted(
        mensal.categorias,
        key=lambda c: c.despesas_positivas_centavos,
        reverse=True,
    )

    for categoria in categorias[:10]:
        linhas.append(
            f"Condominio ID {categoria.condominio_id} "
            f"| {categoria.categoria_chave.upper()} "
            f"| {moeda(categoria.despesas_positivas_centavos)}"
        )

    linhas.extend([
        "",
        "4. ALERTAS DE VARIACAO",
        "",
        f"Total de alertas: {len(alertas)}",
    ])

    if not alertas:
        linhas.append(
            "Nenhum aumento sinalizado pelos criterios atuais."
        )

    for alerta in alertas[:10]:
        linhas.extend([
            "",
            f"Condominio ID {alerta.condominio_id}",
            f"Categoria: {alerta.categoria_chave}",
            (
                "Referencia historica: "
                + moeda(
                    alerta.referencia_mediana_centavos
                )
            ),
            (
                "Despesa atual: "
                + moeda(
                    alerta.valor_atual_centavos
                )
            ),
            (
                "Aumento identificado: "
                + moeda(alerta.aumento_centavos)
            ),
            (
                "Variacao percentual aproximada: "
                f"{alerta.aumento_percentual_inteiro}%"
            ),
            "Recomendacao: conferir documentos, "
            "quantidades, contratos e justificativas.",
        ])

    linhas.extend([
        "",
        "5. RECOMENDACOES ESTRATEGICAS",
        "",
    ])

    if categorias:
        principal = categorias[0]

        linhas.append(
            "Priorizar a revisao da categoria "
            f"{principal.categoria_chave.upper()} "
            f"do condominio ID {principal.condominio_id}, "
            "por apresentar a maior despesa positiva "
            "entre as categorias observadas no mes."
        )

    if alertas:
        linhas.append(
            "Investigar os aumentos sinalizados, "
            "priorizando o maior impacto financeiro."
        )

    linhas.extend([
        "",
        "6. RESSALVAS DA ANALISE",
        "",
        "A cobertura integral do mes precisa ser confirmada.",
        "Categorias e alertas exibem ate dez prioridades.",
        *historico.ressalvas,
        "",
        "CONFIDENCIAL - HAIZE INTELLIGENCE",
        "Uso privado e estrategico.",
    ])

    texto = "\n".join(linhas)

    if len(texto) > 40000:
        raise ValueError(
            "Relatorio excede o limite permitido."
        )

    return texto
