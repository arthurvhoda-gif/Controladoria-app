import { useCallback, useEffect, useRef, useState } from 'react'
import './CentralFinanceira.css'

const moeda = c => c == null ? '—' : (c / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const hoje = () => new Date().toLocaleDateString('en-CA')
const valorParaAPI = valor => {
  const v = String(valor || '').trim()
  if (/^\d+(?:\.\d{3})*,\d{1,2}$/.test(v)) return v.replaceAll('.', '').replace(',', '.')
  if (/^\d+(?:[.,]\d{1,2})?$/.test(v)) return v.replace(',', '.')
  return null
}
const erroHttp = async res => {
  let info
  try { info = await res.json() } catch { /* servidor sem JSON */ }
  return typeof info?.detail === 'string' ? info.detail : `Falha na operação (HTTP ${res.status}).`
}

export default function CentralFinanceira({ apiUrl, token, perfil }) {
  const [itens, setItens] = useState([])
  const [selecionado, setSelecionado] = useState(null)
  const [detalhe, setDetalhe] = useState(null)
  const [busca, setBusca] = useState('')
  const [estado, setEstado] = useState('Carregando dados financeiros...')
  const [erro, setErro] = useState('')
  const [processando, setProcessando] = useState(false)
  const [form, setForm] = useState({ data: hoje(), valor: '', observacao: '', arquivo: null })
  const [usuarios, setUsuarios] = useState([])
  const [vinculoId, setVinculoId] = useState('')
  const [justificativa, setJustificativa] = useState('')
  const [novoUsuario, setNovoUsuario] = useState({ nome: '', email: '', senha: '' })
  const [mostrarCadastro, setMostrarCadastro] = useState(false)
  const chaveRef = useRef(null)
  const headers = { Authorization: `Bearer ${token}` }

  // A consulta pura e compartilhada pelo carregamento inicial e pela atualizacao.
  // Nenhuma resposta pode atravessar sessoes quando o componente desmonta.
  const buscarSolicitacoes = useCallback(async (signal) => {
    const res = await fetch(`${apiUrl}/financeiro/solicitacoes`, {
      headers: { Authorization: `Bearer ${token}` }, cache: 'no-store', signal
    })
    if (!res.ok) throw new Error(await erroHttp(res))
    return res.json()
  }, [apiUrl, token])

  const carregar = useCallback(async (id = null) => {
    const data = await buscarSolicitacoes()
    setItens(data.solicitacoes || [])
    setEstado(`${data.solicitacoes?.length ?? 0} solicitações listadas (limite de ${data.limite}).`)
    if (id != null) {
      const r = await fetch(`${apiUrl}/financeiro/solicitacoes/${id}/lancamentos`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
      if (!r.ok) throw new Error(await erroHttp(r))
      const d = await r.json()
      setDetalhe(d)
      setSelecionado(id)
    }
  }, [apiUrl, token, buscarSolicitacoes])

  useEffect(() => {
    const controller = new AbortController()
    buscarSolicitacoes(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        setItens(data.solicitacoes || [])
        setEstado(`${data.solicitacoes?.length ?? 0} solicitações listadas (limite de ${data.limite}).`)
        setErro('')
      })
      .catch(e => { if (!controller.signal.aborted) setErro(e.message) })
    return () => controller.abort()
  }, [buscarSolicitacoes])

  const abrir = async id => {
    setErro('')
    setDetalhe(null)
    setSelecionado(id)
    setVinculoId('')
    setJustificativa('')
    try { await carregar(id) } catch (e) { setErro(e.message) }
  }
  const atualizarForm = (campo, valor) => {
    chaveRef.current = null
    setForm(p => ({ ...p, [campo]: valor }))
  }

  const enviar = async ev => {
    ev.preventDefault()
    if (perfil !== 'Controladoria' || !selecionado || processando) return
    const valor = valorParaAPI(form.valor)
    if (!valor || Number(valor) <= 0 || !form.arquivo || !form.data) {
      setErro('Informe data, valor positivo e comprovante em PDF, PNG ou JPG.'); return
    }
    if (form.arquivo.size > 5 * 1024 * 1024) {
      setErro('O comprovante não pode ultrapassar 5 MB.'); return
    }
    // Mantém chave durante falha de rede para que uma repetição não lance em dobro.
    if (!chaveRef.current) chaveRef.current = crypto.randomUUID()
    const corpo = new FormData()
    corpo.append('data_pagamento', form.data)
    corpo.append('valor', valor)
    corpo.append('observacao', form.observacao)
    corpo.append('chave_operacao', chaveRef.current)
    corpo.append('comprovante', form.arquivo)
    setProcessando(true); setErro('')
    try {
      const res = await fetch(`${apiUrl}/financeiro/solicitacoes/${selecionado}/pagamentos`, { method: 'POST', headers, body: corpo })
      if (!res.ok) throw new Error(await erroHttp(res))
      chaveRef.current = null
      setForm({ data: hoje(), valor: '', observacao: '', arquivo: null })
      const entrada = document.querySelector('#comprovante-financeiro')
      if (entrada) entrada.value = ''
      await carregar(selecionado)
      setEstado('Pagamento registrado. Confira o saldo e a auditoria abaixo.')
    } catch (e) { setErro(e.message) }
    finally { setProcessando(false) }
  }

  const estornar = async lancamento => {
    if (processando || perfil !== 'Controladoria') return
    const motivo = window.prompt(`Motivo do estorno do lançamento #${lancamento.id} (mínimo 10 caracteres):`)
    if (motivo === null) return
    if (motivo.trim().length < 10) { setErro('Informe justificativa com pelo menos 10 caracteres.'); return }
    if (!window.confirm('Confirmar estorno auditado? O pagamento original será preservado.')) return
    setProcessando(true); setErro('')
    try {
      const res = await fetch(`${apiUrl}/financeiro/lancamentos/${lancamento.id}/estornar`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ motivo: motivo.trim(), chave_operacao: crypto.randomUUID() }),
      })
      if (!res.ok) throw new Error(await erroHttp(res))
      await carregar(selecionado)
      setEstado('Estorno registrado como novo evento; pagamento original preservado.')
    } catch (e) { setErro(e.message) }
    finally { setProcessando(false) }
  }

  const baixar = async lancamento => {
    setErro('')
    try {
      const res = await fetch(`${apiUrl}/financeiro/comprovantes/${lancamento.id}`, { headers })
      if (!res.ok) throw new Error(await erroHttp(res))
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url
      a.download = lancamento.comprovante?.nome || `comprovante-${lancamento.id}`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    } catch (e) { setErro(e.message) }
  }

  const carregarUsuarios = async () => {
    if (perfil !== 'Controladoria') return
    try {
      const r = await fetch(`${apiUrl}/usuarios`, { headers })
      if (!r.ok) throw new Error(await erroHttp(r))
      setUsuarios(await r.json())
    } catch (e) { setErro(e.message) }
  }

  const vincular = async () => {
    if (!selecionado || !vinculoId || justificativa.trim().length < 10 || processando) {
      setErro('Selecione o usuário e informe uma justificativa com pelo menos 10 caracteres.'); return
    }
    if (!window.confirm('Vincular esta solicitação legada ao usuário escolhido? A ação será auditada.')) return
    setProcessando(true); setErro('')
    try {
      const r = await fetch(`${apiUrl}/solicitacoes/${selecionado}/vinculo-solicitante`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario_id: Number(vinculoId), justificativa }),
      })
      if (!r.ok) throw new Error(await erroHttp(r))
      await carregar(selecionado)
      setEstado('Vínculo de usuário corrigido e auditado.')
    } catch (e) { setErro(e.message) }
    finally { setProcessando(false) }
  }

  const cadastrarFinanceiro = async ev => {
    ev.preventDefault()
    if (processando) return
    setProcessando(true); setErro('')
    try {
      const r = await fetch(`${apiUrl}/usuarios`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...novoUsuario, perfil: 'Financeiro' }),
      })
      if (!r.ok) throw new Error(await erroHttp(r))
      setEstado('Usuário Financeiro cadastrado. Repasse a senha por canal seguro e solicite troca no primeiro login.')
      setNovoUsuario({ nome: '', email: '', senha: '' })
      setMostrarCadastro(false)
    } catch (e) { setErro(e.message) }
    finally { setProcessando(false) }
  }

  const filtrados = itens.filter(i => [i.numero, i.condominio, i.fornecedor, i.descricao, i.categoria].some(v =>
    String(v || '').toLocaleLowerCase('pt-BR').includes(busca.toLocaleLowerCase('pt-BR'))))
  const sum = itens.reduce((acc, item) => acc + (item.pago_centavos || 0), 0)
  const excesso = itens.reduce((acc, item) => acc + (item.excedente_centavos || 0), 0)
  const estornos = new Set((detalhe?.lancamentos || []).filter(i => i.tipo === 'estorno').map(i => i.estorno_de_id))

  return <div className="fin-root">
    <header className="fin-title">
      <div><span className="eyebrow">CONTROLE FINANCEIRO • LIVRO DE PAGAMENTOS</span><h2>Central Financeira</h2>
        <p>Pagamentos comprovados, estornos auditados e alertas de excedentes. Valores de pagamento são mantidos em centavos.</p></div>
      <div className="fin-tools">
        <button className="button-secondary" type="button" onClick={() => carregar(selecionado).catch(e => setErro(e.message))}>Atualizar</button>
        {perfil === 'Controladoria' && <button className="button-secondary" type="button" onClick={() => setMostrarCadastro(p => !p)}>Cadastrar Financeiro</button>}
      </div>
    </header>
    {erro && <div className="fin-alerta" role="alert">{erro}</div>}
    <div className="fin-estado" role="status">{estado}</div>
    {mostrarCadastro && perfil === 'Controladoria' && <form className="fin-card fin-cadastro" onSubmit={cadastrarFinanceiro}>
      <h3>Cadastrar usuário do Financeiro</h3><p>Este perfil é exclusivamente de consulta: não registra pagamentos, não estorna e não altera solicitações.</p>
      <label>Nome<input required maxLength={150} value={novoUsuario.nome} onChange={e => setNovoUsuario(p => ({ ...p, nome: e.target.value }))} /></label>
      <label>E-mail<input type="email" required value={novoUsuario.email} onChange={e => setNovoUsuario(p => ({ ...p, email: e.target.value }))} /></label>
      <label>Senha inicial segura<input type="password" required minLength={10} value={novoUsuario.senha} onChange={e => setNovoUsuario(p => ({ ...p, senha: e.target.value }))} /></label>
      <button className="button-primary" type="submit" disabled={processando}>Criar acesso Financeiro</button>
    </form>}
    <section className="fin-kpis">
      <article><span>Pagamentos líquidos</span><strong>{moeda(sum)}</strong></article>
      <article className={excesso > 0 ? 'fin-danger' : ''}><span>Excedentes detectados</span><strong>{moeda(excesso)}</strong></article>
      <article><span>Solicitações listadas</span><strong>{itens.length}</strong></article>
    </section>
    <div className="fin-layout">
      <section className="fin-card fin-lista">
        <label htmlFor="busca-financeiro">Buscar solicitação</label>
        <input id="busca-financeiro" type="search" value={busca} onChange={e => setBusca(e.target.value)} placeholder="Código, condomínio, fornecedor..." />
        <div className="fin-linhas" role="list">
          {filtrados.map(i => <button role="listitem" type="button" key={i.solicitacao_id} onClick={() => abrir(i.solicitacao_id)} className={`fin-linha ${selecionado === i.solicitacao_id ? 'fin-ativa' : ''}`}>
            <span className="fin-linha-top"><strong>{i.numero}</strong><small>{i.status}</small></span>
            <span>{i.condominio} · {i.fornecedor}</span>
            <span className="fin-linha-valor">Pago: <b>{moeda(i.pago_centavos)}</b>{i.alerta_sobrepagamento && <em>Excedente {moeda(i.excedente_centavos)}</em>}</span>
          </button>)}
          {!filtrados.length && <p className="fin-vazio">Nenhuma solicitação localizada.</p>}
        </div>
      </section>
      <section className="fin-card fin-detalhe">
        {!detalhe ? <div className="fin-vazio">Selecione uma solicitação para acompanhar pagamentos e comprovantes.</div> : <>
          <header><h3>{detalhe.resumo.numero} · {detalhe.resumo.condominio}</h3><p>{detalhe.resumo.descricao}</p></header>
          <div className="fin-resumo">
            <span>Solicitado <b>{moeda(detalhe.resumo.solicitado_centavos)}</b></span>
            <span>Aprovado <b>{moeda(detalhe.resumo.aprovado_centavos)}</b></span>
            <span>Realizado <b>{moeda(detalhe.resumo.realizado_centavos)}</b></span>
            <span>Pago <b>{moeda(detalhe.resumo.pago_centavos)}</b></span>
            <span>Saldo versus aprovado <b>{moeda(detalhe.resumo.saldo_centavos)}</b></span>
          </div>
          {detalhe.resumo.alerta_sobrepagamento && <div className="fin-alerta" role="alert"><strong>Alerta de sobrepagamento: {moeda(detalhe.resumo.excedente_centavos)}</strong><p>O pagamento foi registrado, sem bloqueio, e o excedente permanecerá rastreável.</p></div>}
          {detalhe.resumo.solicitante_id == null && perfil === 'Controladoria' && <section className="fin-legado">
            <h4>Solicitação legada sem vínculo de identidade</h4>
            <p>Para preservar o acesso seguro, vincule manualmente após confirmar a autoria. Não será feita atribuição por nome.</p>
            <button className="button-secondary" type="button" onClick={carregarUsuarios}>Carregar usuários</button>
            {usuarios.length > 0 && <>
              <select value={vinculoId} onChange={e => setVinculoId(e.target.value)}><option value="">Selecione usuário</option>{usuarios.filter(u => ['Solicitante', 'Controladoria'].includes(u.perfil)).map(u => <option key={u.id} value={u.id}>{u.nome} · {u.email}</option>)}</select>
              <textarea placeholder="Justificativa da conferência documental (mínimo 10 caracteres)" value={justificativa} onChange={e => setJustificativa(e.target.value)} />
              <button className="button-secondary" type="button" onClick={vincular} disabled={processando}>Vincular e registrar auditoria</button>
            </>}
          </section>}
          {perfil === 'Financeiro' && <p className="fin-aviso">Acesso somente para consulta de saldos, histórico de lançamentos e comprovantes. O registro de pagamentos e os estornos são restritos à Controladoria.</p>}
          {perfil === 'Controladoria' && detalhe.resumo.pagamento_permitido && <form className="fin-form" onSubmit={enviar}>
            <h4>Registrar pagamento</h4>
            <div className="fin-form-grid"><label>Data do pagamento<input type="date" max={hoje()} value={form.data} onChange={e => atualizarForm('data', e.target.value)} required /></label>
            <label>Valor (R$)<input inputMode="decimal" placeholder="700,00" value={form.valor} onChange={e => atualizarForm('valor', e.target.value)} required /></label></div>
            <label>Comprovante (PDF, PNG ou JPG — até 5 MB)<input id="comprovante-financeiro" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e => atualizarForm('arquivo', e.target.files?.[0] || null)} required /></label>
            <label>Observação (opcional)<textarea maxLength={500} value={form.observacao} onChange={e => atualizarForm('observacao', e.target.value)} /></label>
            <button className="button-primary" type="submit" disabled={processando}>{processando ? 'Registrando...' : 'Registrar pagamento auditado'}</button>
          </form>}
          {perfil === 'Controladoria' && !detalhe.resumo.pagamento_permitido && <p className="fin-aviso">Para registrar pagamento, a solicitação precisa estar aprovada e ter valor aprovado positivo.</p>}
          <div className="fin-historico"><h4>Livro de lançamentos e comprovantes</h4>
            {detalhe.lancamentos.length === 0 && <p className="fin-vazio">Nenhum pagamento registrado.</p>}
            {detalhe.lancamentos.map(l => <article className={`fin-evento ${l.tipo === 'estorno' ? 'fin-estorno' : ''}`} key={l.id}>
              <div><strong>#{l.id} · {l.tipo === 'estorno' ? `Estorno do #${l.estorno_de_id}` : 'Pagamento'}</strong><strong>{l.tipo === 'estorno' ? '−' : '+'}{moeda(l.valor_centavos)}</strong></div>
              <small>{l.data_pagamento || l.criado_em?.slice(0, 10)} · {l.autor_nome}</small>
              {l.excedente_centavos_no_lancamento > 0 && <p className="fin-alerta"><b>Alerta histórico:</b> excedente de {moeda(l.excedente_centavos_no_lancamento)} após este lançamento.</p>}
              {l.observacao && <p>{l.observacao}</p>}
              <div className="fin-evento-botoes">
                {l.comprovante && <button type="button" className="button-secondary" onClick={() => baixar(l)}>Baixar comprovante</button>}
                {perfil === 'Controladoria' && l.tipo === 'pagamento' && !estornos.has(l.id) && <button type="button" className="button-secondary" onClick={() => estornar(l)} disabled={processando}>Estornar com justificativa</button>}
                {estornos.has(l.id) && <span className="fin-rotulo-estornado">Estornado</span>}
              </div>
            </article>)}
          </div>
        </>}
      </section>
    </div>
    <p className="fin-nota">O valor aprovado é herdado do cadastro de compras (Float legado); não deve ser confundido com o total efetivamente pago. Os pagamentos são preservados em centavos e comprovados individualmente.</p>
  </div>
}
