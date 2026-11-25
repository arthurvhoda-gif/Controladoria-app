
# -*- coding: utf-8 -*-
"""HAIZE INTELLIGENCE - Relatorio estrategico integrado."""

from collections.abc import Mapping

from intelligence_motor_v78 import analisar_historico_privado

from intelligence_relatorio_v78 import (
    moeda,
    gerar_relatorio_privado_v78,
)

from intelligence_previsao_v78 import (
    ErroPrevisao,
    interpretar_mes,
    prever_despesas_v78,
)

from intelligence_oportunidades_v78 import (
    ErroOportunidades,
    identificar_oportunidades_v78,
)


def gerar_relatorio_integrado_v78(
    registros,
    competencia,
    fechamentos_por_condominio,
):
    """
    Unifica os motores privados da Intelligence.

    Exige fechamento confirmado individualmente
    para cada condominio nas analises preditivas.

    Nao acessa banco, rede ou email.
    Nao altera dados.
    """

    referencia = interpretar_mes(competencia)

    analisar_historico_privado(registros)

    historico = tuple(
        registro
        for registro in registros
        if registro.competencia <= referencia
    )

    if not historico:
        raise ValueError(
            "Historico indisponivel para a competencia."
        )

    condominios = sorted({
        registro.condominio_id
        for registro in historico
    })

    if not isinstance(
        fechamentos_por_condominio,
        Mapping,
    ):
        raise ValueError(
            "Fechamentos por condominio obrigatorios."
        )

    fechamentos = {}

    for cid, meses in fechamentos_por_condominio.items():

        if (
            isinstance(cid, bool)
            or not isinstance(cid, int)
            or cid not in condominios
        ):
            raise ValueError(
                "Condominio invalido nos fechamentos."
            )

        if not isinstance(
            meses,
            (list, tuple, set, frozenset),
        ):
            raise ValueError(
                "Formato de fechamento invalido."
            )

        meses_validados = set()

        for mes in meses:

            data = interpretar_mes(mes)

            if data > referencia:
                raise ValueError(
                    "Fechamento posterior a competencia."
                )

            meses_validados.add(mes)

        fechamentos[cid] = meses_validados

    relatorio_base = gerar_relatorio_privado_v78(
        historico,
        competencia,
    )

    linhas = [
        relatorio_base,
        "",
        "7. INTELIGENCIA PREDITIVA",
        "",
        "Previsao de despesas positivas.",
        "Os cenarios nao sao garantias "
        "nem intervalos de confianca.",
    ]

    oportunidades = []
    condominios_sem_previsao = 0
    categorias_avaliadas = 0
    categorias_sem_base = 0
    condominios_sem_analise = 0

    for cid in condominios:

        dados = tuple(
            registro
            for registro in historico
            if registro.condominio_id == cid
        )

        meses_fechados = fechamentos.get(
            cid,
            set(),
        )

        linhas.extend([
            "",
            f"Condominio ID {cid}",
        ])

        if competencia not in meses_fechados:

            linhas.append(
                "Fechamento mensal nao confirmado. "
                "Previsao nao realizada."
            )

            condominios_sem_previsao += 1
            condominios_sem_analise += 1
            continue

        try:

            previsao = prever_despesas_v78(
                dados,
                cid,
                competencia,
                meses_fechados,
            )

            linhas.extend([
                (
                    "Competencia prevista: "
                    + previsao.competencia_prevista
                ),
                (
                    "Despesa estimada: "
                    + moeda(previsao.previsao_centavos)
                ),
                (
                    "Cenario inferior: "
                    + moeda(
                        previsao.cenario_inferior_centavos
                    )
                ),
                (
                    "Cenario superior: "
                    + moeda(
                        previsao.cenario_superior_centavos
                    )
                ),
                (
                    "Erro medio retrospectivo: "
                    + moeda(
                        previsao.erro_medio_centavos
                    )
                ),
                f"Metodo: {previsao.metodo}",
                (
                    "Meses analisados: "
                    f"{previsao.meses_analisados}"
                ),
            ])

        except ErroPrevisao:

            condominios_sem_previsao += 1

            linhas.append(
                "Historico insuficiente para previsao."
            )

        try:

            resultado = identificar_oportunidades_v78(
                dados,
                cid,
                competencia,
                meses_fechados,
            )

            categorias_avaliadas += (
                resultado.categorias_avaliadas
            )

            categorias_sem_base += (
                resultado.categorias_sem_base
            )

            oportunidades.extend(
                resultado.oportunidades
            )

        except ErroOportunidades:

            condominios_sem_analise += 1

    linhas.extend([
        "",
        (
            "Condominios sem previsao: "
            f"{condominios_sem_previsao}"
        ),
        "",
        "8. OPORTUNIDADES DE REDUCAO DE CUSTOS",
        "",
        f"Categorias avaliadas: {categorias_avaliadas}",
        f"Categorias sem base: {categorias_sem_base}",
        (
            "Condominios sem analise de oportunidades: "
            f"{condominios_sem_analise}"
        ),
        (
            "Oportunidades identificadas: "
            f"{len(oportunidades)}"
        ),
    ])

    oportunidades.sort(
        key=lambda item: (
            -item.impacto_adicional_centavos,
            item.condominio_id,
            item.categoria,
        )
    )

    impacto_total = sum(
        item.impacto_adicional_centavos
        for item in oportunidades
    )

    linhas.append(
        "Impacto adicional identificado: "
        + moeda(impacto_total)
    )

    if not oportunidades:

        linhas.append(
            "Nenhuma oportunidade sinalizada "
            "nas categorias avaliaveis."
        )

    for item in oportunidades[:15]:

        linhas.extend([
            "",
            f"Condominio ID {item.condominio_id}",
            f"Categoria: {item.categoria.upper()}",
            f"Prioridade: {item.prioridade}",
            (
                "Referencia mensal: "
                + moeda(
                    item.referencia_mensal_centavos
                )
            ),
            (
                "Total dos tres meses recentes: "
                + moeda(
                    item.total_recente_centavos
                )
            ),
            (
                "Impacto adicional: "
                + moeda(
                    item.impacto_adicional_centavos
                )
            ),
            (
                "Meses com aumento: "
                f"{item.meses_com_aumento}"
            ),
            f"Acao recomendada: {item.recomendacao}",
        ])

    linhas.extend([
        "",
        "9. LIMITACOES E PLANO DE ACAO",
        "",
        "O impacto adicional nao representa economia "
        "garantida ou recuperavel.",
        "Previsoes dependem da qualidade do historico.",
        "O fechamento precisa ser confirmado por condominio.",
        "O relatorio detalha ate quinze oportunidades.",
        "Priorizar a investigacao dos maiores impactos.",
        "Validar documentos e causas antes de decidir.",
        "Registrar as economias efetivamente comprovadas.",
        "",
        "CONFIDENCIAL - HAIZE INTELLIGENCE",
    ])

    texto = "\n".join(linhas)

    if len(texto) > 40000:
        raise ValueError(
            "Relatorio integrado excede o limite."
        )

    return texto
