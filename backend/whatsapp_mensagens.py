"""Previa OFFLINE de avisos WhatsApp de serviços internos (V6.3).

Não usa banco, rede, API de WhatsApp nem altera o fluxo de servicos.
A mensagem e o link são gerados a partir de dados já existentes.
A URL é informada explicitamente ou por uma futura integração.
"""

from urllib.parse import urlsplit, urlunsplit
import re


_EVENTOS = (
    ("Nova tarefa para executar:", "nova_tarefa", "Uma nova tarefa foi atribuída a você."),
    ("Você foi designado para fiscalizar:", "designacao_fiscal", "Você foi designado para fiscalizar uma tarefa."),
    ("Serviço pronto para fiscalização:", "pronto_fiscalizacao", "Uma tarefa está pronta para fiscalização."),
    ("Serviço devolvido para ajustes:", "devolucao", "Uma tarefa foi devolvida para ajustes."),
    ("Serviço aguardando validação final:", "validacao_final", "Uma tarefa aguarda validação final."),
    ("Serviço validado:", "servico_validado", "Uma tarefa foi validada e encerrada."),
)


def _texto_unica_linha(valor, limite=80):
    """Evita que titulos com quebras injetem instruções na mensagem."""
    texto = re.sub(r"\s+", " ", str(valor or "")).strip()
    return texto[:limite].rstrip() or "Sem título"


def link_direto_servico(servico_id, frontend_public_url):
    """Gera um link de tarefa; aceita HTTP apenas em localhost para testes."""
    if isinstance(servico_id, bool) or not isinstance(servico_id, int) or servico_id <= 0:
        raise ValueError("ID de serviço inválido")
    if not isinstance(frontend_public_url, str) or not frontend_public_url.strip():
        raise ValueError("FRONTEND_PUBLIC_URL deve ser configurada explicitamente")
    valor = frontend_public_url.strip()
    if any(c.isspace() for c in valor):
        raise ValueError("URL do frontend não pode conter espaços")
    partes = urlsplit(valor)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ValueError("URL do frontend inválida")
    if partes.username is not None or partes.password is not None:
        raise ValueError("Credenciais não podem estar na URL")
    try:
        _ = partes.port
    except ValueError as exc:
        raise ValueError("Porta da URL inválida") from exc
    if partes.scheme == "http" and partes.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("Links públicos devem usar HTTPS")
    if partes.path not in ("", "/") or partes.query or partes.fragment:
        raise ValueError("Informe somente a origem do frontend, sem caminhos ou parâmetros")
    return urlunsplit((partes.scheme, partes.netloc, "/", f"servico={servico_id}", ""))


def classificar_aviso(mensagem_aviso):
    """Classificação a partir dos prefixos atuais de servicos_api.py."""
    texto = str(mensagem_aviso or "")
    for prefixo, codigo, descricao in _EVENTOS:
        if texto.startswith(prefixo):
            return codigo, descricao
    return "atualizacao", "Existe uma atualização em uma tarefa."


def preparar_previa_whatsapp(*, servico_id, titulo, mensagem_aviso, frontend_public_url, tipo_evento=None):
    """Devolve dados de uma prévia, sem salvar nem enviar qualquer mensagem."""
    link = link_direto_servico(servico_id, frontend_public_url)
    # NULL identifica legado; tipo invalido nao usa classificacao pelo texto.
    if tipo_evento is None:
        codigo, descricao = classificar_aviso(mensagem_aviso)
    else:
        codigo, descricao = 'atualizacao', 'Existe uma atualização em uma tarefa.'
        if isinstance(tipo_evento, str):
            for _, candidato, texto in _EVENTOS:
                if candidato == tipo_evento:
                    codigo, descricao = candidato, texto
                    break
    titulo_limpo = _texto_unica_linha(titulo)
    texto = (
        "CONTROLADORIA HAIZE\n"
        f"{descricao}\n"
        f"Solicitação: #{servico_id:04d}\n"
        f"Serviço: {titulo_limpo}\n"
        "Consulte os detalhes e registre suas ações no aplicativo:\n"
        f"{link}"
    )
    return {"evento": codigo, "servico_id": servico_id, "link": link, "mensagem": texto}
