# -*- coding: utf-8 -*-
"""V7.7: protótipo de persistência transacional, BLOQUEADO FORA DE SQLITE EM MEMÓRIA.

Não há rota HTTP, CLI, agendador ou importação automática neste módulo.
Este código não é importado por main.py. Antes do uso real, exigir revisão de
permissões, conciliação documental, migração e autorização expressa.
"""
from dataclasses import dataclass
import hashlib
from sqlalchemy import select

import models
from custos_historicos_v77 import (
    CustoImportacaoLoteV77, CustoHistoricoEventoV77, CustoHistoricoV77,
)
from custos_importacao_v77 import (
    ErroValidacaoCustos, LancamentoValidado, chave_nome,
    montar_previa, validar_lote,
)


@dataclass(frozen=True)
class ResultadoPersistenciaV77:
    novos: int
    alterados: int
    inalterados: int
    ausentes_na_origem: int
    valor_total_centavos: int
    lote_id: int | None


def _somente_sqlite_descartavel(sessao):
    bind = sessao.get_bind()
    if bind.dialect.name != "sqlite" or str(bind.url.database) != ":memory:":
        raise RuntimeError("V7.7: escrita permitida somente em SQLite em memória nesta etapa")


def _conferir_cadastros(sessao, mapa_condominios):
    """Os IDs/nome vêm da revisão manual. Não inserir condomínios por aproximação."""
    normalizado = {chave_nome(nome): cid for nome, cid in mapa_condominios.items()}
    ids = set(normalizado.values())
    cadastros = sessao.execute(
        select(models.Condominio.id, models.Condominio.nome)
        .where(models.Condominio.id.in_(ids))
    ).all()
    if len(cadastros) != len(ids):
        raise ErroValidacaoCustos("cadastro: condomínio inexistente")
    for cid, nome in cadastros:
        if normalizado.get(chave_nome(nome)) != cid:
            raise ErroValidacaoCustos("cadastro: ID não corresponde ao nome aprovado")


def _registrados(sessao, dados):
    """Lê apenas os condomínios e a origem presentes no lote validado."""
    ids = {r.condominio_id for r in dados}
    origem = {r.origem for r in dados}
    if len(origem) != 1:
        raise ErroValidacaoCustos("lote: origens misturadas")
    objs = sessao.scalars(
        select(CustoHistoricoV77)
        .where(CustoHistoricoV77.condominio_id.in_(ids))
        .where(CustoHistoricoV77.origem == next(iter(origem)))
    ).all()
    return {(obj.condominio_id, obj.origem, obj.id_origem): obj for obj in objs}


def _hash_lote(dados):
    serial = "\n".join(
        f"{r.condominio_id}/{r.origem}/{r.id_origem}/{r.hash_conteudo}"
        for r in sorted(dados, key=lambda r: r.chave)
    )
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


def ensaiar_aplicacao_sqlite_v77(
    sessao, registros, mapa_condominios, *, cobertura_completa=False
):
    """Insere/atualiza em uma transação gerida pelo CHAMADOR, somente em memória.

    - valida lote INTEIRO antes de alterar o banco;
    - nunca cria condomínios, nunca exclui custos;
    - segunda importação idêntica não cria lote ou eventos extras;
    - todas as alterações ficam pendentes até o commit explícito do chamador.
    """
    _somente_sqlite_descartavel(sessao)
    dados = validar_lote(registros, mapa_condominios)
    _conferir_cadastros(sessao, mapa_condominios)
    encontrados = _registrados(sessao, dados)
    # "montar_previa" compara hash de lançamentos validados; os objetos
    # persistidos são projetados em snapshots com mesmas chaves e hashes.
    fotografias = {
        chave: LancamentoValidado(
            condominio_id=obj.condominio_id, origem=obj.origem,
            id_origem=obj.id_origem, data_original=obj.data_original,
            competencia=obj.competencia, descricao=obj.descricao,
            categoria_original=obj.categoria_original,
            categoria_chave=obj.categoria_chave,
            valor_centavos=obj.valor_centavos, hash_conteudo=obj.hash_conteudo,
        ) for chave, obj in encontrados.items()
    }
    previa = montar_previa(dados, fotografias, cobertura_completa=cobertura_completa)
    if previa.novos == previa.alterados == 0:
        return ResultadoPersistenciaV77(
            novos=0, alterados=0, inalterados=previa.inalterados,
            ausentes_na_origem=previa.ausentes_na_origem,
            valor_total_centavos=previa.total_centavos, lote_id=None,
        )

    lote = CustoImportacaoLoteV77(
        origem=dados[0].origem, arquivo_sha256=_hash_lote(dados),
        status="ensaio_sqlite", qtd_registros=len(dados),
        total_centavos=previa.total_centavos,
    )
    sessao.add(lote)
    sessao.flush()

    for item in dados:
        antigo = encontrados.get(item.chave)
        if antigo is not None and antigo.hash_conteudo == item.hash_conteudo:
            continue
        if antigo is None:
            atual = CustoHistoricoV77(
                condominio_id=item.condominio_id, origem=item.origem,
                id_origem=item.id_origem, data_original=item.data_original,
                competencia=item.competencia, descricao=item.descricao,
                categoria_original=item.categoria_original,
                categoria_chave=item.categoria_chave,
                valor_centavos=item.valor_centavos, hash_conteudo=item.hash_conteudo,
                lote_primeira_entrada_id=lote.id,
                lote_ultima_atualizacao_id=lote.id,
            )
            sessao.add(atual)
            sessao.flush()
            acao, anterior = "inclusao", None
        else:
            atual = antigo
            anterior = antigo.hash_conteudo
            atual.data_original = item.data_original
            atual.competencia = item.competencia
            atual.descricao = item.descricao
            atual.categoria_original = item.categoria_original
            atual.categoria_chave = item.categoria_chave
            atual.valor_centavos = item.valor_centavos
            atual.hash_conteudo = item.hash_conteudo
            atual.lote_ultima_atualizacao_id = lote.id
            acao = "atualizacao"
        sessao.add(CustoHistoricoEventoV77(
            custo_historico_id=atual.id, lote_id=lote.id,
            acao=acao, hash_anterior=anterior, hash_novo=item.hash_conteudo,
        ))
    sessao.flush()
    return ResultadoPersistenciaV77(
        novos=previa.novos, alterados=previa.alterados,
        inalterados=previa.inalterados,
        ausentes_na_origem=previa.ausentes_na_origem,
        valor_total_centavos=previa.total_centavos, lote_id=lote.id,
    )
