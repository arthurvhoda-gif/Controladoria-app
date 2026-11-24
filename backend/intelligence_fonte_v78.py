
# -*- coding: utf-8 -*-
"""
HAIZE INTELLIGENCE V7.8
Fonte histórica privada de dados financeiros.

Objetivo:
- Ler os lançamentos históricos validados da V7.7.
- Conferir os vínculos com os condomínios.
- Verificar a integridade dos registros.
- Entregar os dados ao motor de inteligência.

SEGURANÇA:
- Somente SQLite em memória nesta etapa.
- Nenhuma gravação no banco.
- Nenhuma rota HTTP.
- Nenhum envio de e-mail.
- Nenhuma conexão com produção.
"""

from collections.abc import Mapping
from decimal import Decimal

from sqlalchemy import select

import models

from custos_historicos_v77 import CustoHistoricoV77

from custos_importacao_v77 import (
    ORIGEM,
    chave_nome,
    validar_lote,
)

from intelligence_motor_v78 import (
    LIMITE_LANCAMENTOS,
    analisar_historico_privado,
)


class ErroFonteIntelligence(ValueError):
    """Erro de validação sem exposição de dados financeiros."""


def _verificar_ambiente(sessao):
    """Bloqueia qualquer banco que não seja SQLite em memória."""

    if sessao is None or not hasattr(sessao, "get_bind"):
        raise ErroFonteIntelligence(
            "Sessão de banco inválida."
        )

    
    if sessao.new or sessao.dirty or sessao.deleted:
        raise ErroFonteIntelligence(
            "Sessao possui alteracoes pendentes."
        )

    bind = sessao.get_bind()


    if (
        bind.dialect.name != "sqlite"
        or getattr(bind, "url", None) is None
        or bind.url.database != ":memory:"
    ):
        raise RuntimeError(
            "HAIZE INTELLIGENCE V7.8: "
            "acesso permitido somente em SQLite em memória."
        )


def _validar_condominios(sessao, mapa_condominios):
    """Confere vínculos explícitos entre nomes e IDs cadastrados."""

    if (
        not isinstance(mapa_condominios, Mapping)
        or not mapa_condominios
    ):
        raise ErroFonteIntelligence(
            "Mapeamento de condomínios obrigatório."
        )

    nomes_por_id = {}
    nomes_normalizados = set()

    for nome, condominio_id in mapa_condominios.items():

        nome_normalizado = chave_nome(nome)

        if (
            not nome_normalizado
            or isinstance(condominio_id, bool)
            or not isinstance(condominio_id, int)
            or condominio_id <= 0
        ):
            raise ErroFonteIntelligence(
                "Mapeamento de condomínios inválido."
            )

        if (
            nome_normalizado in nomes_normalizados
            or condominio_id in nomes_por_id
        ):
            raise ErroFonteIntelligence(
                "Mapeamento de condomínios duplicado."
            )

        nomes_normalizados.add(nome_normalizado)
        nomes_por_id[condominio_id] = nome

    cadastros = sessao.execute(
        select(
            models.Condominio.id,
            models.Condominio.nome,
        ).where(
            models.Condominio.id.in_(
                list(nomes_por_id.keys())
            )
        )
    ).all()

    if len(cadastros) != len(nomes_por_id):
        raise ErroFonteIntelligence(
            "Existe condomínio sem cadastro correspondente."
        )

    for condominio_id, nome_cadastrado in cadastros:

        nome_aprovado = nomes_por_id[condominio_id]

        if chave_nome(nome_cadastrado) != chave_nome(nome_aprovado):
            raise ErroFonteIntelligence(
                "Nome e identificador do condomínio não correspondem."
            )

    return nomes_por_id


def carregar_historico_validado_v78(
    sessao,
    mapa_condominios,
):
    """
    Carrega despesas históricas de uma sessão de testes.

    Todos os registros são revalidados antes de serem
    entregues ao motor de inteligência.

    Não altera objetos, tabelas ou lançamentos.
    """

    _verificar_ambiente(sessao)

    nomes_por_id = _validar_condominios(
        sessao,
        mapa_condominios,
    )

    registros_banco = sessao.scalars(
        select(CustoHistoricoV77)
        .where(
            CustoHistoricoV77.condominio_id.in_(
                list(nomes_por_id.keys())
            )
        )
        .where(
            CustoHistoricoV77.origem == ORIGEM
        )
        .order_by(
            CustoHistoricoV77.condominio_id,
            CustoHistoricoV77.id_origem,
        )
        .limit(LIMITE_LANCAMENTOS + 1)
    ).all()

    if not registros_banco:
        raise ErroFonteIntelligence(
            "Nenhum lançamento histórico disponível para análise."
        )

    if len(registros_banco) > LIMITE_LANCAMENTOS:
        raise ErroFonteIntelligence(
            "Quantidade de lançamentos acima do limite permitido."
        )

    registros_brutos = []

    for registro in registros_banco:

        if (
            isinstance(registro.valor_centavos, bool)
            or not isinstance(registro.valor_centavos, int)
        ):
            raise ErroFonteIntelligence(
                "Registro histórico com valor inválido."
            )

        valor_decimal = (
            Decimal(registro.valor_centavos)
            / Decimal(100)
        )

        registros_brutos.append({
            "id": registro.id_origem,
            "condominio": nomes_por_id[
                registro.condominio_id
            ],
            "descricao": registro.descricao,
            "data": registro.data_original,
            "valor": format(valor_decimal, ".2f"),
            "categoria": registro.categoria_original,
        })

    registros_validados = validar_lote(
        registros_brutos,
        mapa_condominios,
    )

    # Conferir novamente os hashes e metadados
    # armazenados, sem recalcular silenciosamente
    # valores divergentes.

    for original, validado in zip(
        registros_banco,
        registros_validados,
    ):

        if (
            original.hash_conteudo != validado.hash_conteudo
            or original.condominio_id != validado.condominio_id
            or original.id_origem != validado.id_origem
            or original.competencia != validado.competencia
            or original.categoria_chave != validado.categoria_chave
            or original.valor_centavos != validado.valor_centavos
        ):
            raise ErroFonteIntelligence(
                "Divergência de integridade no histórico financeiro."
            )

    return registros_validados


def analisar_fonte_historica_v78(
    sessao,
    mapa_condominios,
):
    """
    Executa o fluxo privado:

    Banco de testes
        -> Validação V7.7
        -> Conferência de integridade
        -> Motor HAIZE INTELLIGENCE V7.8

    Retorna o resultado estruturado da análise.

    Não envia relatórios e não modifica o banco.
    """

    registros = carregar_historico_validado_v78(
        sessao,
        mapa_condominios,
    )

    return analisar_historico_privado(registros)
