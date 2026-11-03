"""Protecao conservadora contra exclusao de usuarios com servicos pendentes.

Nao altera tarefas, nao migra dados e nao envia avisos. Regras de outros modulos
nao sao cobertas por este helper e devem ser verificadas separadamente.
"""
from sqlalchemy import or_
import models
from servicos_api import STATUS_FECHADO


def contar_servicos_pendentes(db, usuario_id: int) -> int:
    """Conta servicos abertos distintos em que a pessoa e criadora ou participante."""
    participa = (
        db.query(models.ServicoParticipante.id)
        .filter(
            models.ServicoParticipante.servico_id == models.ServicoInterno.id,
            models.ServicoParticipante.usuario_id == usuario_id,
        )
        .exists()
    )
    return (
        db.query(models.ServicoInterno.id)
        .filter(models.ServicoInterno.status != STATUS_FECHADO)
        .filter(or_(models.ServicoInterno.criador_id == usuario_id, participa))
        .count()
    )
