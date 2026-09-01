import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer
} from 'recharts'
import './App.css'

const API_URL = 'https://controladoria-api.onrender.com'

function App() {
  const [usuarioLogado, setUsuarioLogado] = useState(() => {
    const salvo = localStorage.getItem('usuarioControladoria')
    return salvo ? JSON.parse(salvo) : null
  })

  const [emailLogin, setEmailLogin] = useState('')
  const [senhaLogin, setSenhaLogin] = useState('')
  const [carregandoLogin, setCarregandoLogin] = useState(false)
  const [pagina, setPagina] = useState(usuarioLogado?.perfil === 'Solicitante' ? 'solicitacoes' : 'dashboard')

  const [backendOnline, setBackendOnline] = useState(false)
  const [solicitacoes, setSolicitacoes] = useState([])
  const [condominios, setCondominios] = useState([])
  const [fornecedores, setFornecedores] = useState([])
  const [categorias, setCategorias] = useState([])

  const [toasts, setToasts] = useState([])
  const [dialog, setDialog] = useState({
    isOpen: false, type: 'confirm', title: '', message: '', inputValue: '',
    confirmText: 'Confirmar', cancelText: 'Cancelar', isDanger: false, onConfirm: null
  })

  const [solicitacaoEditando, setSolicitacaoEditando] = useState(null)
  const [solicitacaoSelecionada, setSolicitacaoSelecionada] = useState(null)
  const [historicoSolicitacao, setHistoricoSolicitacao] = useState([])

  const [anexosSolicitacao, setAnexosSolicitacao] = useState([])
  const [fazendoUpload, setFazendoUpload] = useState(false)

  const [mostrarFormulario, setMostrarFormulario] = useState(false)
  const [condominioEditando, setCondominioEditando] = useState(null)
  const [mostrarFormularioCondominio, setMostrarFormularioCondominio] = useState(false)
  
  const [fornecedorEditando, setFornecedorEditando] = useState(null)
  const [mostrarFormularioFornecedor, setMostrarFormularioFornecedor] = useState(false)
  
  const [categoriaEditando, setCategoriaEditando] = useState(null)
  const [mostrarFormularioCategoria, setMostrarFormularioCategoria] = useState(false)

  const [filtroSolicitacao, setFiltroSolicitacao] = useState('')
  const [filtroStatus, setFiltroStatus] = useState('todos')
  const [filtroCompra, setFiltroCompra] = useState('')
  const [salvando, setSalvando] = useState(false)

  const [filtroMesAnalise, setFiltroMesAnalise] = useState('todos')
  const [filtroCondominioAnalise, setFiltroCondominioAnalise] = useState('todos')

  const [formulario, setFormulario] = useState({
    condominio: '', categoria: '', fornecedor: '', descricao: '',
    valor_servico: '', valor_produto: '', observacao: ''
  })

  const [formularioCondominio, setFormularioCondominio] = useState({
    nome: '', cnpj: '', codigo: ''
  })

  const [formularioFornecedor, setFormularioFornecedor] = useState({
    nome: '', cnpj: '', categoria: ''
  })

  const [formularioCategoria, setFormularioCategoria] = useState({
    nome: '', descricao: '', limites: {} 
  })

  function getAuthHeaders(isFormData = false) {
    const headers = {}
    if (!isFormData) headers['Content-Type'] = 'application/json'
    if (usuarioLogado?.token) headers['Authorization'] = `Bearer ${usuarioLogado.token}`
    return headers
  }

  async function extrairErro(res, mensagemPadrao) {
    try {
      const data = await res.json()
      return data.detail || mensagemPadrao
    } catch {
      return mensagemPadrao
    }
  }

  async function fazerLogin(e) {
    e.preventDefault()
    setCarregandoLogin(true)
    try {
      const res = await fetch(`${API_URL}/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: emailLogin, senha: senhaLogin }) })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao entrar')
        throw new Error(erroMsg)
      }
      const dados = await res.json()
      const dadosUsuario = { ...dados.usuario, token: dados.access_token }
      setUsuarioLogado(dadosUsuario)
      localStorage.setItem('usuarioControladoria', JSON.stringify(dadosUsuario))
      mostrarToast(`Bem-vindo(a), ${dadosUsuario.nome}!`, 'success')
      setPagina(dadosUsuario.perfil === 'Solicitante' ? 'solicitacoes' : 'dashboard')
    } catch (err) { mostrarToast(err.message, 'error') } finally { setCarregandoLogin(false) }
  }

  function fazerLogout() {
    setUsuarioLogado(null)
    localStorage.removeItem('usuarioControladoria')
    setEmailLogin('')
    setSenhaLogin('')
  }

  function mostrarToast(mensagem, tipo = 'success') {
    const id = Date.now()
    setToasts(prev => [...prev, { id, mensagem, tipo }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }

  function confirmarAcao(titulo, mensagem, onConfirm, isDanger = false) { setDialog({ isOpen: true, type: 'confirm', title: titulo, message: mensagem, inputValue: '', confirmText: 'Sim, confirmar', cancelText: 'Cancelar', isDanger, onConfirm }) }
  function pedirInput(titulo, mensagem, valorPadrao, onConfirm, isDanger = false) { setDialog({ isOpen: true, type: 'prompt', title: titulo, message: mensagem, inputValue: valorPadrao || '', confirmText: 'Salvar', cancelText: 'Cancelar', isDanger, onConfirm }) }
  function fecharDialog() { setDialog(prev => ({ ...prev, isOpen: false, inputValue: '' })) }
  function handleConfirmDialog() { if (dialog.onConfirm) { dialog.type === 'prompt' ? dialog.onConfirm(dialog.inputValue) : dialog.onConfirm() } fecharDialog() }

  async function verificarBackend() { try { const resposta = await fetch(`${API_URL}/status`); setBackendOnline(resposta.ok) } catch { setBackendOnline(false) } }

  async function carregarDados() {
    if (!usuarioLogado) return
    try {
      const [resSol, resCond, resForn, resCat] = await Promise.all([
        fetch(`${API_URL}/solicitacoes`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/condominios`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/fornecedores`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/categorias`, { headers: getAuthHeaders() })
      ])

      if (resSol.ok) {
        let dados = await resSol.json()
        if (usuarioLogado.perfil === 'Solicitante') dados = dados.filter(s => s.solicitante === usuarioLogado.nome)
        setSolicitacoes(dados)
        if (solicitacaoSelecionada) {
          const atual = dados.find(i => i.id === solicitacaoSelecionada.id)
          setSolicitacaoSelecionada(atual || null)
        }
      }
      if (resCond.ok) setCondominios(await resCond.json())
      if (resForn.ok) setFornecedores(await resForn.json())
      if (resCat.ok) setCategorias(await resCat.json())
    } catch (e) { }
  }

  useEffect(() => {
    if (usuarioLogado) {
      verificarBackend()
      carregarDados()
      const int = setInterval(() => { verificarBackend(); carregarDados() }, 5000)
      return () => clearInterval(int)
    }
  }, [usuarioLogado])

  function numero(v) {
    if (v === null || v === undefined || v === '') return 0
    let normalizado = String(v).replace(/[^0-9.,-]/g, '')
    if (normalizado.includes('.') && normalizado.includes(',')) normalizado = normalizado.replace(/\./g, '').replace(',', '.')
    else normalizado = normalizado.replace(',', '.')
    const resultado = parseFloat(normalizado)
    return Number.isFinite(resultado) ? resultado : 0
  }

  function solicitado(item) { return numero(item?.valor) }
  function aprovado(item) { return numero(item?.valor_aprovado) }
  function realizado(item) { return numero(item?.valor_realizado) }
  function formatarValor(v) { return numero(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) }
  function formatarNumero(v) { return numero(v).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) }
  function formatarDataHora(dataStr) { if (!dataStr) return '-'; try { const d = new Date(dataStr); return isNaN(d.getTime()) ? dataStr : d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return dataStr } }
  function formatarMesAno(yyyyMM) { try { if (!yyyyMM || typeof yyyMM !== 'string' || !yyyyMM.includes('-')) return String(yyyyMM || ''); const [ano, mes] = yyyMM.split('-'); const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']; const indice = parseInt(mes, 10) - 1; if (indice >= 0 && indice <= 11) return `${meses[indice]}/${ano}`; return yyyMM } catch (e) { return String(yyyyMM || '') } }
  function normalizarTexto(v) { return String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim() }

  function textoStatus(status) {
    const n = normalizarTexto(status)
    if (n === 'finalizada' || n === 'finalizado' || n.includes('finalizada') || n.includes('finalizado')) return 'Finalizada'
    if (n === 'em execucao' || n.includes('em execucao') || n === 'execucao') return 'Em execução'
    if (n === 'ajuste solicitado' || n.includes('ajuste')) return 'Ajuste solicitado'
    if (n === 'reprovada' || n === 'reprovado') return 'Reprovada'
    if (n === 'aprovada' || n === 'aprovado' || n === 'pagamento aprovado' || n.includes('pagamento aprovado')) return 'Aprovada'
    if (n === 'em analise' || n.includes('em analise')) return 'Em análise'
    return 'Aprovação pendente'
  }

  function renderBadge(sol) {
    if (!sol) return null
    const statusStr = typeof sol === 'string' ? sol : sol.status
    let txt = textoStatus(statusStr)
    if (typeof sol === 'object') {
      const vSol = solicitado(sol)
      const vApr = aprovado(sol)
      if (txt === 'Aprovada' && vApr > 0 && vApr < vSol) txt = 'Aprovada Parcialmente'
    }

    let backgroundColor = '#FEF3C7'; let color = '#D97706'
    if (txt === 'Aprovada') { backgroundColor = '#DBEAFE'; color = '#2563EB' }
    if (txt === 'Aprovada Parcialmente') { backgroundColor = '#FEF3C7'; color = '#b45309' }
    if (txt === 'Em execução') { backgroundColor = '#E0E7FF'; color = '#4F46E5' }
    if (txt === 'Finalizada') { backgroundColor = '#D1FAE5'; color = '#059669' }
    if (txt === 'Ajuste solicitado') { backgroundColor = '#FEF3C7'; color = '#D97706' }
    if (txt === 'Reprovada') { backgroundColor = '#FEE2E2'; color = '#DC2626' }
    if (txt === 'Em análise') { backgroundColor = '#E0F2FE'; color = '#0284C7' }

    return (<span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: '600', backgroundColor, color, display: 'inline-block' }}>{txt}</span>)
  }

  function classeVariacao(valor) { return numero(valor) > 0 ? 'positive' : numero(valor) < 0 ? 'negative' : 'neutral' }

  const quantidadePendentes = solicitacoes.filter(item => textoStatus(item.status) === 'Aprovação pendente').length
  const valorTotalSolicitado = solicitacoes.reduce((total, item) => total + solicitado(item), 0)
  const valorTotalAprovado = solicitacoes.reduce((total, item) => ['Aprovada', 'Em execução', 'Finalizada'].includes(textoStatus(item.status)) ? total + (aprovado(item) || solicitado(item)) : total, 0)
  const valorTotalRealizado = solicitacoes.reduce((total, item) => textoStatus(item.status) === 'Finalizada' ? total + (realizado(item) || aprovado(item) || solicitado(item)) : total, 0)
  const economiaTotal = valorTotalSolicitado - valorTotalRealizado

  const solicitacoesFiltradas = solicitacoes.filter(sol => {
    const t = normalizarTexto(`${sol.numero || ''} ${sol.condominio || ''} ${sol.categoria || ''} ${sol.descricao || ''} ${textoStatus(sol.status) || ''}`)
    const matchBusca = !filtroSolicitacao || t.includes(normalizarTexto(filtroSolicitacao))
    const matchStatus = filtroStatus === 'todos' || textoStatus(sol.status) === filtroStatus
    return matchBusca && matchStatus
  })

  const comprasFiltradas = solicitacoes.filter(sol => {
    const t = normalizarTexto(`${sol.numero || ''} ${sol.condominio || ''} ${sol.categoria || ''} ${sol.descricao || ''}`)
    return (!filtroCompra || t.includes(normalizarTexto(filtroCompra)))
  })

  const maioresSolicitacoes = [...solicitacoes].sort((a, b) => solicitado(b) - solicitado(a)).slice(0, 5)
  const mesesDisponiveis = [...new Set(solicitacoes.map(s => { if (!s.data || typeof s.data !== 'string') return null; return s.data.substring(0, 7) }).filter(Boolean))].sort().reverse()

  const solicitacoesAnaliseFiltradas = solicitacoes.filter(sol => {
    const nomeCondominio = sol.condominio || ''
    const matchCondominio = filtroCondominioAnalise === 'todos' || nomeCondominio === filtroCondominioAnalise
    let matchMes = filtroMesAnalise === 'todos'
    if (filtroMesAnalise !== 'todos' && sol.data && typeof sol.data === 'string') matchMes = sol.data.substring(0, 7) === filtroMesAnalise
    return matchCondominio && matchMes
  })

  const gastosPorCondominio = solicitacoesAnaliseFiltradas.reduce((acc, sol) => {
    const c = sol.condominio || 'Sem condomínio'; acc[c] = (acc[c] || 0) + solicitado(sol); return acc
  }, {})

  const dadosGraficoCondominios = Object.keys(gastosPorCondominio).map(nome => {
    const sols = solicitacoesAnaliseFiltradas.filter(s => (s.condominio || 'Sem condomínio') === nome)
    return {
      name: nome, Solicitado: sols.reduce((a, s) => a + solicitado(s), 0),
      Aprovado: sols.reduce((a, s) => ['Aprovada', 'Em execução', 'Finalizada'].includes(textoStatus(s.status)) ? a + (aprovado(s) || solicitado(s)) : a, 0),
      Realizado: sols.reduce((a, s) => textoStatus(s.status) === 'Finalizada' ? a + (realizado(s) || aprovado(s) || solicitado(s)) : a, 0)
    }
  }).sort((a, b) => b.Solicitado - a.Solicitado).slice(0, 10)

  const orcamentoPorCondominio = solicitacoesAnaliseFiltradas.reduce((acc, sol) => {
    const cond = sol.condominio || 'Sem condomínio'
    if (!acc[cond]) acc[cond] = { aprovado: 0, realizado: 0 }
    const statusAtual = textoStatus(sol.status)
    if (['Aprovada', 'Em execução', 'Finalizada'].includes(statusAtual)) acc[cond].aprovado += aprovado(sol) || solicitado(sol)
    if (statusAtual === 'Finalizada') acc[cond].realizado += realizado(sol) || aprovado(sol) || solicitado(sol)
    return acc
  }, {})

  const listaOrcamentoCondominio = Object.entries(orcamentoPorCondominio).map(([nome, d]) => ({ nome, ...d, saldo: d.aprovado - d.realizado })).sort((a, b) => b.aprovado - a.aprovado)


  function atualizarCampoFormulario(campo, valor) { setFormulario(atual => ({ ...atual, [campo]: valor })) }
  function limparFormulario() { setFormulario({ condominio: '', categoria: '', fornecedor: '', descricao: '', valor_servico: '', valor_produto: '', observacao: '' }); setSolicitacaoEditando(null) }
  function fecharFormulario() { setMostrarFormulario(false); limparFormulario() }

  function editarSolicitacao(solicitacao) {
    setSolicitacaoEditando(solicitacao)
    setFormulario({
      condominio: solicitacao.condominio || '', categoria: solicitacao.categoria || '', fornecedor: solicitacao.fornecedor || '',
      descricao: solicitacao.descricao || '', valor_servico: solicitacao.valor_servico || '', valor_produto: solicitacao.valor_produto || '', observacao: solicitacao.observacao || ''
    })
    setMostrarFormulario(true)
    setSolicitacaoSelecionada(null)
  }

  async function salvarSolicitacao(e) {
    e.preventDefault()
    if (!formulario.condominio || !formulario.categoria || !formulario.fornecedor || !formulario.descricao || !formulario.observacao) { mostrarToast('Por favor, preencha todos os campos obrigatórios (*).', 'error'); return }
    const vServ = numero(formulario.valor_servico)
    const vProd = numero(formulario.valor_produto)
    if (vServ <= 0 && vProd <= 0) { mostrarToast('O valor total (Serviço ou Produto) deve ser maior que zero.', 'error'); return }

    const payload = { ...formulario, valor_servico: vServ, valor_produto: vProd, solicitante: usuarioLogado.nome, status: 'Aprovação pendente' }

    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/solicitacoes${solicitacaoEditando ? `/${solicitacaoEditando.id}` : ''}`, { method: solicitacaoEditando ? 'PUT' : 'POST', headers: getAuthHeaders(), body: JSON.stringify(payload) })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar solicitação.')
        throw new Error(erroMsg)
      }
      await carregarDados()
      fecharFormulario()
      mostrarToast(solicitacaoEditando ? 'Atualizada com sucesso!' : 'Enviada com sucesso!', 'success')
    } catch (erro) { mostrarToast(erro.message, 'error') } finally { setSalvando(false) }
  }

  async function abrirSolicitacao(solicitacao) {
    setSolicitacaoSelecionada(solicitacao)
    setHistoricoSolicitacao([])
    setAnexosSolicitacao([])
    try {
      const resHist = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/historico`, { headers: getAuthHeaders() })
      if (resHist.ok) setHistoricoSolicitacao(await resHist.json())
      const resAnexos = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/anexos`, { headers: getAuthHeaders() })
      if (resAnexos.ok) setAnexosSolicitacao(await resAnexos.json())
    } catch (e) { }
  }

  function fecharSolicitacao() { setSolicitacaoSelecionada(null); setHistoricoSolicitacao([]); setAnexosSolicitacao([]) }

  async function fazerUploadAnexo(evento, tipoDocumento) {
    const arquivo = evento.target.files[0]
    if (!arquivo) return
    if (arquivo.size > 10 * 1024 * 1024) { mostrarToast('O arquivo deve ter no máximo 10MB', 'error'); return }

    const formData = new FormData()
    formData.append('arquivo', arquivo)
    formData.append('tipo', tipoDocumento)
    formData.append('responsavel', usuarioLogado.nome)

    setFazendoUpload(true)
    try {
      const res = await fetch(`${API_URL}/solicitacoes/${solicitacaoSelecionada.id}/anexos`, { method: 'POST', headers: getAuthHeaders(true), body: formData })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao anexar arquivo.')
        throw new Error(erroMsg)
      }
      mostrarToast('Arquivo anexado!', 'success')
      await abrirSolicitacao(solicitacaoSelecionada)
    } catch (e) { mostrarToast(e.message, 'error') } finally { setFazendoUpload(false) }
  }

  function aprovarSolicitacao(solicitacao) {
    pedirInput('Aprovar solicitação', 'Informe o valor aprovado para essa compra:', String(aprovado(solicitacao) || solicitado(solicitacao) || ''), async v => {
      const vNum = numero(v)
      if (vNum <= 0) { mostrarToast('O valor aprovado deve ser maior que zero.', 'error'); return }
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, { method: 'PUT', headers: getAuthHeaders(), body: JSON.stringify({ status: 'Aprovada', valor_aprovado: vNum }) })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao aprovar solicitação.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Solicitação aprovada.', 'success')
        fecharSolicitacao()
      } catch (e) { mostrarToast(e.message, 'error') }
    })
  }

  function iniciarExecucao(solicitacao) {
    confirmarAcao('Executar solicitação', `Deseja executar a solicitação ${solicitacao.numero || ''}?`, async () => {
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/iniciar-execucao`, { method: 'PUT', headers: getAuthHeaders(), body: JSON.stringify({ observacao_execucao: '' }) })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao executar a solicitação.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Solicitação enviada para execução!', 'success')
        fecharSolicitacao()
      } catch (e) { mostrarToast(e.message, 'error') }
    })
  }

  function finalizarSolicitacao(solicitacao) {
    pedirInput('Finalizar solicitação', 'Informe o valor realmente realizado/pago:', String(realizado(solicitacao) || aprovado(solicitacao) || solicitado(solicitacao) || ''), async v => {
      const vNum = numero(v)
      if (vNum <= 0) { mostrarToast('O valor realizado deve ser maior que zero.', 'error'); return }
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/finalizar`, { method: 'PUT', headers: getAuthHeaders(), body: JSON.stringify({ valor_realizado: vNum }) })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao finalizar solicitação.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Solicitação finalizada!', 'success')
        fecharSolicitacao()
      } catch (e) { mostrarToast(e.message, 'error') }
    })
  }

  function excluirSolicitacao(solicitacao) {
    confirmarAcao('Excluir', `Apagar ${solicitacao.numero || ''}?`, async () => {
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao excluir solicitação.')
          throw new Error(erroMsg)
        }
        if (solicitacaoSelecionada?.id === solicitacao.id) fecharSolicitacao()
        await carregarDados()
        mostrarToast('Excluída.', 'success')
      } catch (e) { mostrarToast(e.message, 'error') }
    }, true)
  }

  function fecharFormularioCondominio() { setMostrarFormularioCondominio(false); setCondominioEditando(null); setFormularioCondominio({ nome: '', cnpj: '', codigo: '' }) }
  function abrirFormularioNovoCondominio() { limparFormularioCondominio(); setMostrarFormularioCondominio(true) }
  function editarCondominio(cond) { setCondominioEditando(cond); setFormularioCondominio({ nome: cond.nome || '', cnpj: cond.cnpj || '', codigo: cond.codigo || '' }); setMostrarFormularioCondominio(true) }
  
  async function salvarCondominio(e) {
    e.preventDefault()
    if (!formularioCondominio.nome) return
    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/condominios${condominioEditando ? `/${condominioEditando.id}` : ''}`, { method: condominioEditando ? 'PUT' : 'POST', headers: getAuthHeaders(), body: JSON.stringify(formularioCondominio) })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar condomínio.')
        throw new Error(erroMsg)
      }
      const salvo = await res.json()
      await carregarDados()
      fecharFormularioCondominio()
      if (mostrarFormulario && !condominioEditando) atualizarCampoFormulario('condominio', salvo.nome)
      mostrarToast('Salvo!', 'success')
    } catch (err) { mostrarToast(err.message, 'error') } finally { setSalvando(false) }
  }

  function excluirCondominio(id, nome) {
    confirmarAcao('Excluir', `Apagar "${nome}"?`, async () => {
      try {
        const res = await fetch(`${API_URL}/condominios/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao excluir condomínio.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Excluído.', 'success')
      } catch (e) { mostrarToast(e.message, 'error') }
    }, true)
  }

  function fecharFormularioCategoria() { setMostrarFormularioCategoria(false); setCategoriaEditando(null); setFormularioCategoria({ nome: '', descricao: '', limites: {} }) }
  function abrirFormularioNovoCategoria() { setCategoriaEditando(null); setFormularioCategoria({ nome: '', descricao: '', limites: {} }); setMostrarFormularioCategoria(true) }
  
  function editarCategoria(cat) { 
    setCategoriaEditando(cat)
    const limitesObj = {}
    if (cat.limites && Array.isArray(cat.limites)) {
      cat.limites.forEach(l => { limitesObj[l.condominio] = formatarNumero(l.limite) })
    }
    setFormularioCategoria({ nome: cat.nome || '', descricao: cat.descricao || '', limites: limitesObj })
    setMostrarFormularioCategoria(true) 
  }
  
  async function salvarCategoria(e) {
    e.preventDefault()
    if (!formularioCategoria.nome) return

    const limitesArray = Object.entries(formularioCategoria.limites).map(([condominio, limite]) => ({
      condominio: condominio, limite: numero(limite)
    })).filter(l => l.limite > 0) 

    const payload = { nome: formularioCategoria.nome, descricao: formularioCategoria.descricao, limites: limitesArray }

    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/categorias${categoriaEditando ? `/${categoriaEditando.id}` : ''}`, {
        method: categoriaEditando ? 'PUT' : 'POST', headers: getAuthHeaders(), body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar categoria.')
        throw new Error(erroMsg)
      }
      const salvo = await res.json()
      await carregarDados()
      fecharFormularioCategoria()
      if (mostrarFormulario && !categoriaEditando) atualizarCampoFormulario('categoria', salvo.nome)
      mostrarToast('Categoria Salva!', 'success')
    } catch (err) { 
      mostrarToast(err.message, 'error') 
    } finally { 
      setSalvando(false) 
    }
  }

  function excluirCategoria(id, nome) {
    confirmarAcao('Excluir', `Apagar a categoria "${nome}"?`, async () => {
      try {
        const res = await fetch(`${API_URL}/categorias/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao excluir categoria.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Categoria excluída.', 'success')
      } catch (e) { mostrarToast(e.message, 'error') }
    }, true)
  }

  function fecharFormularioFornecedor() { setMostrarFormularioFornecedor(false); setFornecedorEditando(null); setFormularioFornecedor({ nome: '', cnpj: '', categoria: '' }) }
  function abrirFormularioNovoFornecedor() { setFornecedorEditando(null); setFormularioFornecedor({ nome: '', cnpj: '', categoria: '' }); setMostrarFormularioFornecedor(true) }
  function editarFornecedor(forn) { setFornecedorEditando(forn); setFormularioFornecedor({ nome: forn.nome || '', cnpj: forn.cnpj || '', categoria: forn.categoria || '' }); setMostrarFormularioFornecedor(true) }
  
  async function salvarFornecedor(e) {
    e.preventDefault()
    if (!formularioFornecedor.nome) return
    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/fornecedores${fornecedorEditando ? `/${fornecedorEditando.id}` : ''}`, { method: fornecedorEditando ? 'PUT' : 'POST', headers: getAuthHeaders(), body: JSON.stringify(formularioFornecedor) })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar fornecedor.')
        throw new Error(erroMsg)
      }
      const salvo = await res.json()
      await carregarDados()
      fecharFormularioFornecedor()
      if (mostrarFormulario && !fornecedorEditando) atualizarCampoFormulario('fornecedor', salvo.nome)
      mostrarToast('Salvo!', 'success')
    } catch (err) { mostrarToast(err.message, 'error') } finally { setSalvando(false) }
  }

  function excluirFornecedor(id, nome) {
    confirmarAcao('Excluir', `Apagar "${nome}"?`, async () => {
      try {
        const res = await fetch(`${API_URL}/fornecedores/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao excluir fornecedor.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Excluído.', 'success')
      } catch (e) { mostrarToast(e.message, 'error') }
    }, true)
  }

  function atualizarCampoFornecedor(campo, valor) {
    setFormularioFornecedor(atual => ({ ...atual, [campo]: valor }))
  }

  if (!usuarioLogado) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', width: '100vw', backgroundColor: '#f8fafc', backgroundImage: 'radial-gradient(circle at 50% -20%, #dbeafe, #f8fafc 60%)' }}>
        <div className="toast-container">
          {toasts.map(t => (<div key={t.id} className={`toast ${t.tipo}`}><span className="toast-icon">{t.tipo === 'success' ? '✓' : '!'}</span><span>{t.mensagem}</span></div>))}
        </div>
        <div style={{ background: '#ffffff', padding: '40px', borderRadius: '16px', boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)', width: '100%', maxWidth: '420px', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ width: '64px', height: '64px', background: 'linear-gradient(135deg, #3b82f6, #2563eb)', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '32px', fontWeight: '800', color: 'white', margin: '0 0 24px 0' }}>C</div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', color: '#0f172a', margin: '0 0 8px 0' }}>Controladoria</h2>
          <p style={{ fontSize: '14px', color: '#64748b', textAlign: 'center', margin: '0 0 32px 0' }}>Acesso restrito ao sistema.</p>
          <form onSubmit={fazerLogin} style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '13px', fontWeight: '600', color: '#475569' }}>E-mail</label>
              <input type="email" placeholder="Seu e-mail" value={emailLogin} onChange={e => setEmailLogin(e.target.value)} required style={{ width: '100%', padding: '12px 16px', fontSize: '15px', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '13px', fontWeight: '600', color: '#475569' }}>Senha</label>
              <input type="password" placeholder="••••••••" value={senhaLogin} onChange={e => setSenhaLogin(e.target.value)} required style={{ width: '100%', padding: '12px 16px', fontSize: '15px', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px' }} />
            </div>
            <button type="submit" disabled={carregandoLogin} style={{ marginTop: '8px', padding: '14px', fontSize: '16px', width: '100%', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '8px', fontWeight: '600', cursor: 'pointer' }}>{carregandoLogin ? 'Entrando...' : 'Entrar'}</button>
          </form>
        </div>
      </div>
    )
  }

  const ehControladoria = usuarioLogado.perfil === 'Controladoria'

  return (
    <div className="app">
      <div className="toast-container">
        {toasts.map(toast => (<div key={toast.id} className={`toast ${toast.tipo}`}><span className="toast-icon">{toast.tipo === 'success' ? '✓' : '!'}</span><span>{toast.mensagem}</span></div>))}
      </div>

      {dialog.isOpen && (
        <div style={{ zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)' }} onClick={e => { if (e.target === e.currentTarget) fecharDialog() }}>
          <div style={{ width: '100%', maxWidth: '400px', backgroundColor: '#ffffff', padding: '24px', borderRadius: '12px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)', display: 'flex', flexDirection: 'column', gap: '16px', animation: 'slideUp 0.2s ease-out' }}>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>{dialog.title}</h3>
            <p style={{ margin: 0, fontSize: '14px', color: '#475569' }}>{dialog.message}</p>
            {dialog.type === 'prompt' && (
              <input type="text" value={dialog.inputValue} onChange={e => setDialog(p => ({ ...p, inputValue: e.target.value }))} autoFocus onKeyDown={e => { if (e.key === 'Enter') handleConfirmDialog() }} style={{ width: '100%', padding: '12px 16px', border: '1px solid #cbd5e1', borderRadius: '8px', fontSize: '15px', outline: 'none', boxSizing: 'border-box' }} />
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
              <button type="button" className="button-secondary" onClick={fecharDialog}>{dialog.cancelText}</button>
              <button type="button" className={dialog.isDanger ? 'button-danger' : 'button-primary'} onClick={handleConfirmDialog}>{dialog.confirmText}</button>
            </div>
          </div>
        </div>
      )}

      {/* SIDEBAR COM CORREÇÃO DE SCROLL E FIXAÇÃO DO BOTÃO DE SAIR */}
      <aside className="sidebar" style={{ display: 'flex', flexDirection: 'column', height: '100vh', position: 'sticky', top: 0, overflowY: 'auto' }}>
        <div className="brand" style={{ flexShrink: 0 }}>
          <div className="brand-mark">G</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <strong style={{ fontSize: '18px' }}>Controladoria</strong>
            <span style={{ fontSize: '12px', opacity: 0.8 }}>Haize</span>
          </div>
        </div>

        <nav className="sidebar-nav" style={{ flex: 1 }}>
          <button className={pagina === 'dashboard' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('dashboard')}><span className="nav-icon">◈</span><span>Dashboard</span></button>
          <button className={pagina === 'analises' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('analises')}><span className="nav-icon">◠</span><span>Análises</span></button>
          <button className={pagina === 'solicitacoes' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('solicitacoes')}><span className="nav-icon">▣</span><span>Solicitações</span>{ehControladoria && quantidadePendentes > 0 && (<span className="nav-count">{quantidadePendentes}</span>)}</button>
          <button className={pagina === 'compras' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('compras')}><span className="nav-icon">◫</span><span>Compras</span></button>
          
          <div style={{ margin: '16px 0 8px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }}></div>
          
          <button className={pagina === 'condominios' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('condominios')}><span className="nav-icon">🏢</span><span>Condomínios</span></button>
          <button className={pagina === 'categorias' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('categorias')}><span className="nav-icon">🏷️</span><span>Categorias</span></button>
          <button className={pagina === 'fornecedores' ? 'nav-item active' : 'nav-item'} onClick={() => setPagina('fornecedores')}><span className="nav-icon">🤝</span><span>Fornecedores</span></button>
        </nav>

        <div style={{ flexShrink: 0, marginTop: 'auto', paddingBottom: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column', gap: '12px', background: '#0f172a' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', padding: '0 8px', textAlign: 'center' }}>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'white' }}>{usuarioLogado.nome}</span>
            <span style={{ fontSize: '10px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 'bold' }}>Perfil: {usuarioLogado.perfil}</span>
          </div>
          <button onClick={fazerLogout} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', width: '100%', padding: '8px', backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', fontSize: '12px', fontWeight: '600', cursor: 'pointer' }}>
            <span style={{ fontSize: '14px' }}>🚪</span>Sair do sistema
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="breadcrumb">
              Controladoria {' / '} {pagina === 'dashboard' ? 'Dashboard' : pagina === 'solicitacoes' ? 'Solicitações' : pagina}
            </span>
            <h1>{pagina === 'dashboard' ? 'Visão geral' : pagina === 'solicitacoes' ? ehControladoria ? 'Aprovações' : 'Minhas Solicitações' : pagina.charAt(0).toUpperCase() + pagina.slice(1)}</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" onClick={() => carregarDados()}>↻</button>
            <button className="new-request" onClick={() => setMostrarFormulario(true)}>+ Nova solicitação</button>
          </div>
        </header>

        {pagina === 'dashboard' && (
          <div className="page">
            <section className="kpi-grid">
              <div className="kpi-card"><div className="kpi-top"><span>Solicitado</span><span className="kpi-icon">$</span></div><strong>{formatarValor(valorTotalSolicitado)}</strong></div>
              <div className="kpi-card"><div className="kpi-top"><span>Aprovado</span><span className="kpi-icon success">✓</span></div><strong>{formatarValor(valorTotalAprovado)}</strong></div>
              <div className="kpi-card"><div className="kpi-top"><span>Realizado</span><span className="kpi-icon">◫</span></div><strong>{formatarValor(valorTotalRealizado)}</strong></div>
              <div className="kpi-card highlight"><div className="kpi-top"><span>Economia</span><span className="kpi-icon success">↓</span></div><strong>{formatarValor(economiaTotal)}</strong></div>
            </section>

            <section className="dashboard-grid">
              <div className="panel">
                <div className="panel-header"><div><span className="eyebrow">DESTAQUES</span><h3>Maiores Solicitações</h3></div></div>
                <div className="table">
                  <div className="table-header"><span>ID</span><span>Condomínio</span><span>Valor Total</span><span>Status</span></div>
                  {maioresSolicitacoes.slice(0, 5).map(sol => (
                    <div className="table-row clickable" key={sol.id} onClick={() => abrirSolicitacao(sol)}>
                      <span className="id">{sol.numero}</span>
                      <span>{sol.condominio}</span>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong>{formatarValor(sol.valor)}</strong>
                        {aprovado(sol) > 0 && aprovado(sol) < sol.valor && (<span style={{ fontSize: '11px', color: '#d97706', fontWeight: '600' }}>Aprov: {formatarValor(aprovado(sol))}</span>)}
                        {realizado(sol) > 0 && (<span style={{ fontSize: '11px', color: realizado(sol) <= (aprovado(sol) || sol.valor) ? '#059669' : '#dc2626', fontWeight: '600' }}>Utilizado: {formatarValor(realizado(sol))}</span>)}
                      </div>
                      {renderBadge(sol)}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>
        )}

        {pagina === 'analises' && (
          <div className="page">
            <section className="welcome" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div><span className="eyebrow">ANÁLISES E RELATÓRIOS</span><h2>Visão Analítica Global</h2></div>
              <div style={{ display: 'flex', gap: '16px' }}>
                <select value={filtroCondominioAnalise} onChange={e => setFiltroCondominioAnalise(e.target.value)} style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '8px', backgroundColor: '#fff', fontSize: '14px', color: 'var(--text-primary)', outline: 'none', cursor: 'pointer' }}>
                  <option value="todos">Todos os Condomínios</option>
                  {condominios?.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                </select>
                <select value={filtroMesAnalise} onChange={e => setFiltroMesAnalise(e.target.value)} style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '8px', backgroundColor: '#fff', fontSize: '14px', color: 'var(--text-primary)', outline: 'none', cursor: 'pointer' }}>
                  <option value="todos">Todos os Meses</option>
                  {mesesDisponiveis?.map(m => (<option key={m} value={m}>{formatarMesAno(m)}</option>))}
                </select>
              </div>
            </section>

            <section className="dashboard-grid" style={{ marginTop: '24px' }}>
              <div className="panel" style={{ gridColumn: '1 / -1' }}>
                <div className="panel-header" style={{ justifyContent: 'center', textAlign: 'center' }}>
                  <div><span className="eyebrow">COMPARATIVO</span><h3>Solicitado × Aprovado × Realizado</h3></div>
                </div>
                <div style={{ width: '100%', height: 400, marginTop: '20px' }}>
                  {dadosGraficoCondominios.length === 0 ? (<div className="empty" style={{ textAlign: 'center', padding: '40px' }}>Sem dados para gerar gráfico para o filtro selecionado.</div>) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dadosGraficoCondominios} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} tickFormatter={v => `R$ ${v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v}`} />
                        <RechartsTooltip formatter={v => formatarValor(v)} cursor={{ fill: '#f8fafc' }} />
                        <Legend wrapperStyle={{ paddingTop: '20px' }} />
                        <Bar dataKey="Solicitado" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="Aprovado" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="Realizado" fill="#10b981" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </section>

            <div style={{ marginTop: '48px', marginBottom: '16px' }}><span className="eyebrow">RELATÓRIOS GERENCIAIS DE FECHAMENTO</span></div>

            <section className="dashboard-grid">
              <div className="panel" style={{ gridColumn: '1 / -1' }}>
                <div className="panel-header"><div><span className="eyebrow">POR CENTRO DE CUSTO</span><h3>Relatório de Execução por Condomínio</h3></div></div>
                <div className="table">
                  <div className="table-header" style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr' }}>
                    <span>Condomínio</span><span>Teto Aprovado</span><span>Gasto Realizado</span><span>Saldo (R$)</span><span>Status Orçamentário</span>
                  </div>
                  {listaOrcamentoCondominio.length === 0 ? (<div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>Nenhuma solicitação encontrada para o filtro.</div>) : (
                    listaOrcamentoCondominio.map(item => {
                      let sBadge = 'neutral'; let sTexto = 'No Limite'
                      if (item.saldo > 0) { sBadge = 'positive'; sTexto = 'Economia' }
                      if (item.saldo < 0) { sBadge = 'negative'; sTexto = 'Estourado' }
                      if (item.aprovado === 0) { sBadge = 'neutral'; sTexto = 'Sem Orçamento' }
                      return (
                        <div className="table-row" key={item.nome} style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr' }}>
                          <strong>{item.nome}</strong><span>{formatarValor(item.aprovado)}</span><span>{formatarValor(item.realizado)}</span>
                          <strong className={classeVariacao(item.saldo)}>{formatarValor(item.saldo)}</strong>
                          <span className={`badge ${sBadge}`}>{sTexto}</span>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            </section>
          </div>
        )}

        {(pagina === 'solicitacoes' || pagina === 'compras') && (
          <div className="page">
            <section className="panel">
              <div className="panel-header" style={{ display: 'flex', alignItems: 'center' }}>
                <div><span className="eyebrow">CONTROLE</span><h3>{pagina === 'solicitacoes' ? 'Solicitações de Compra' : 'Compras em Andamento'}</h3></div>
                <div style={{ display: 'flex', gap: '16px' }}>
                  {pagina === 'solicitacoes' && (
                    <select style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '8px', backgroundColor: '#fff' }} value={filtroStatus} onChange={e => setFiltroStatus(e.target.value)}>
                      <option value="todos">Todos os Status</option>
                      <option value="Aprovação pendente">Aprovação pendente</option>
                      <option value="Aprovada">Aprovada</option>
                      <option value="Em execução">Em execução</option>
                      <option value="Finalizada">Finalizada</option>
                    </select>
                  )}
                  <input style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '8px' }} type="text" placeholder="Buscar..." value={pagina === 'solicitacoes' ? filtroSolicitacao : filtroCompra} onChange={e => pagina === 'solicitacoes' ? setFiltroSolicitacao(e.target.value) : setFiltroCompra(e.target.value)} />
                </div>
              </div>
              <div className="table">
                <div className="table-header"><span>ID</span><span>Condomínio</span><span>Descrição</span>{pagina === 'compras' && (<span>Solicitado</span>)}<span>{pagina === 'compras' ? 'Aprovado' : 'Total'}</span><span>Status</span></div>
                {(pagina === 'solicitacoes' ? solicitacoesFiltradas : comprasFiltradas).map(sol => (
                  <div className="table-row clickable" key={sol.id} onClick={() => abrirSolicitacao(sol)}>
                    <span className="id">{sol.numero}</span><span>{sol.condominio}</span>
                    <span>
                      {sol.descricao}
                      {sol.categoria && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>📁 {sol.categoria}</div>}
                    </span>
                    {pagina === 'compras' && (<strong>{formatarValor(sol.valor)}</strong>)}
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <strong>{formatarValor(pagina === 'compras' ? (aprovado(sol) || sol.valor) : sol.valor)}</strong>
                      {pagina === 'solicitacoes' && aprovado(sol) > 0 && aprovado(sol) < sol.valor && (<span style={{ fontSize: '11px', color: '#d97706', fontWeight: '600' }}>Aprov: {formatarValor(aprovado(sol))}</span>)}
                      {realizado(sol) > 0 && (<span style={{ fontSize: '11px', color: realizado(sol) <= (aprovado(sol) || sol.valor) ? '#059669' : '#dc2626', fontWeight: '600' }}>Utilizado: {formatarValor(realizado(sol))}</span>)}
                    </div>
                    {renderBadge(sol)}
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* ABA CATEGORIAS */}
        {pagina === 'categorias' && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">CADASTRO</span><h3>Categorias de Despesa</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoCategoria}>+ Nova Categoria</button>
              </div>
              <div className="company-grid">
                {categorias.map(cat => {
                  const nome = cat.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.categoria === nome).length
                  const limitesCadastrados = cat.limites?.length || 0

                  return (
                    <div className="company-card" key={cat.id}>
                      <div className="company-card-top">
                        <div className="company-avatar" style={{ background: '#fdf4ff', color: '#7e22ce' }}>{String(nome).charAt(0).toUpperCase()}</div>
                        <span className="badge neutral">Ativo</span>
                      </div>
                      <h4>{nome}</h4>
                      {cat.descricao && (<span className="company-detail" style={{ fontStyle: 'italic' }}>{cat.descricao}</span>)}
                      
                      {limitesCadastrados > 0 && (
                        <div style={{ marginTop: '12px', fontSize: '12px', color: '#059669', background: '#ecfdf5', padding: '6px 12px', borderRadius: '6px', fontWeight: '600' }}>
                          Regra Automática ativa em {limitesCadastrados} {limitesCadastrados === 1 ? 'condomínio' : 'condomínios'}
                        </div>
                      )}

                      <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '16px', paddingTop: '16px', display: 'flex', justifyContent: 'space-between' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="text-button" onClick={() => editarCategoria(cat)}>Editar</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirCategoria(cat.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>
        )}

        {/* ABA CONDOMINIOS */}
        {pagina === 'condominios' && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">CADASTRO</span><h3>Condomínios</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoCondominio}>+ Novo Condomínio</button>
              </div>
              <div className="company-grid">
                {condominios.map(condominio => {
                  const nome = condominio.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.condominio === nome).length
                  return (
                    <div className="company-card" key={condominio.id}>
                      <div className="company-card-top">
                        <div className="company-avatar">{String(nome).charAt(0).toUpperCase()}</div>
                        <span className="badge approved">Ativo</span>
                      </div>
                      <h4>{nome}</h4>
                      {condominio.cnpj && (<span className="company-detail">CNPJ: {condominio.cnpj}</span>)}
                      
                      <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '16px', paddingTop: '16px', display: 'flex', justifyContent: 'space-between' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="text-button" onClick={() => editarCondominio(condominio)}>Editar</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirCondominio(condominio.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>
        )}

        {/* ABA FORNECEDORES */}
        {pagina === 'fornecedores' && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">CADASTRO</span><h3>Fornecedores</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoFornecedor}>+ Novo Fornecedor</button>
              </div>
              <div className="company-grid">
                {fornecedores.map(fornecedor => {
                  const nome = fornecedor.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.fornecedor === nome).length
                  return (
                    <div className="company-card" key={fornecedor.id}>
                      <div className="company-card-top">
                        <div className="company-avatar" style={{ background: '#f1f5f9', color: '#475569' }}>{String(nome).charAt(0).toUpperCase()}</div>
                        <span className="badge neutral">Ativo</span>
                      </div>
                      <h4>{nome}</h4>
                      {fornecedor.cnpj && (<span className="company-detail">CNPJ: {fornecedor.cnpj}</span>)}
                      <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '16px', paddingTop: '16px', display: 'flex', justifyContent: 'space-between' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="text-button" onClick={() => editarFornecedor(fornecedor)}>Editar</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirFornecedor(fornecedor.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>
        )}

        {/* MODAL DETALHES DA SOLICITAÇÃO */}
        {solicitacaoSelecionada && (
          <div className="modal-overlay" style={{ zIndex: 100 }} onClick={e => { if (e.target === e.currentTarget) fecharSolicitacao() }}>
            <div className="modal modal-large">
              <div className="modal-header">
                <div><span className="eyebrow">DETALHES</span><h3>{solicitacaoSelecionada.numero}</h3></div>
                <button className="modal-close" onClick={fecharSolicitacao}>×</button>
              </div>
              <div className="modal-body">
                {(() => {
                  const vSol = solicitado(solicitacaoSelecionada); const vApr = aprovado(solicitacaoSelecionada); const vReal = realizado(solicitacaoSelecionada)
                  const temCorte = vApr > 0 && vApr < vSol; const taFinalizado = vReal > 0; const limite = vApr > 0 ? vApr : vSol; const estourou = taFinalizado && vReal > limite
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
                      {temCorte && (
                        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', padding: '12px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '20px' }}>⚠️</span>
                          <div>
                            <strong style={{ display: 'block', fontSize: '14px', color: '#b45309', marginBottom: '4px' }}>Aprovação Parcial</strong>
                            <span style={{ fontSize: '13px', color: '#d97706' }}>Esta solicitação foi aprovada com o valor de <strong>{formatarValor(vApr)}</strong>, que é inferior ao valor original solicitado de <strong>{formatarValor(vSol)}</strong>.</span>
                          </div>
                        </div>
                      )}
                      {taFinalizado && (
                        <div style={{ background: estourou ? '#fef2f2' : '#f0fdf4', border: `1px solid ${estourou ? '#fecaca' : '#bbf7d0'}`, padding: '12px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '20px' }}>{estourou ? '🚨' : '✅'}</span>
                          <div>
                            <strong style={{ display: 'block', fontSize: '14px', color: estourou ? '#991b1b' : '#15803d', marginBottom: '4px' }}>{estourou ? 'Orçamento Ultrapassado' : 'Dentro do Orçamento'}</strong>
                            <span style={{ fontSize: '13px', color: estourou ? '#b91c1c' : '#166534' }}>
                              O valor finalizado (utilizado) foi de <strong>{formatarValor(vReal)}</strong>.
                              {estourou ? ` Esse valor ultrapassou o limite aprovado de ${formatarValor(limite)}.` : ` Excelente! O gasto se manteve dentro do limite aprovado de ${formatarValor(limite)}.`}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                <div className="detail-grid">
                  <div className="detail-card"><span>Status</span><strong>{renderBadge(solicitacaoSelecionada)}</strong></div>
                  
                  {solicitacaoSelecionada.categoria && (
                    <div className="detail-card" style={{ background: '#faf5ff', borderColor: '#f3e8ff' }}>
                      <span>Categoria</span><strong style={{ color: '#7e22ce' }}>📁 {solicitacaoSelecionada.categoria}</strong>
                    </div>
                  )}

                  <div className="detail-card"><span>Valor Serviço</span><strong>{formatarValor(solicitacaoSelecionada.valor_servico)}</strong></div>
                  <div className="detail-card"><span>Valor Produto</span><strong>{formatarValor(solicitacaoSelecionada.valor_produto)}</strong></div>
                  <div className="detail-card" style={{ background: '#eff6ff', borderColor: '#bfdbfe' }}><span>Total Solicitado</span><strong style={{ color: '#1d4ed8' }}>{formatarValor(solicitacaoSelecionada.valor)}</strong></div>

                  {aprovado(solicitacaoSelecionada) > 0 && (<div className="detail-card" style={{ background: '#f0fdf4', borderColor: '#bbf7d0' }}><span>Valor Aprovado</span><strong style={{ color: '#15803d' }}>{formatarValor(solicitacaoSelecionada.valor_aprovado)}</strong></div>)}
                  {realizado(solicitacaoSelecionada) > 0 && (<div className="detail-card" style={{ background: realizado(solicitacaoSelecionada) <= (aprovado(solicitacaoSelecionada) || solicitado(solicitacaoSelecionada)) ? '#f0fdf4' : '#fef2f2', borderColor: realizado(solicitacaoSelecionada) <= (aprovado(solicitacaoSelecionada) || solicitado(solicitacaoSelecionada)) ? '#bbf7d0' : '#fecaca' }}><span>Valor Realizado</span><strong style={{ color: realizado(solicitacaoSelecionada) <= (aprovado(solicitacaoSelecionada) || solicitado(solicitacaoSelecionada)) ? '#15803d' : '#b91c1c' }}>{formatarValor(solicitacaoSelecionada.valor_realizado)}</strong></div>)}
                </div>

                <div className="detail-section" style={{ background: '#f8fafc', padding: '24px', borderRadius: '12px', border: '1px solid #cbd5e1' }}>
                  <div className="section-title-row"><div><span className="eyebrow">DOCUMENTAÇÃO</span><h4 style={{ margin: 0 }}>Arquivos e Comprovantes</h4></div></div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                    {anexosSolicitacao.length === 0 ? (<div style={{ padding: '16px', background: 'white', border: '1px dashed #cbd5e1', borderRadius: '8px', textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)' }}>Nenhum arquivo anexado ainda.</div>) : (
                      anexosSolicitacao.map(anexo => (
                        <div key={anexo.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span style={{ fontSize: '24px' }}>📄</span>
                            <div>
                              <strong style={{ display: 'block', fontSize: '14px', color: 'var(--text-primary)' }}>{anexo.nome_arquivo}</strong>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600' }}>{String(anexo.tipo || '').toUpperCase()} • Enviado em: {formatarDataHora(anexo.data_upload)}</span>
                            </div>
                          </div>
                          <a href={`${API_URL}/anexos/${anexo.id}/download`} target="_blank" rel="noreferrer" className="button-secondary" style={{ padding: '8px 16px', fontSize: '12px' }}>Baixar Arquivo</a>
                        </div>
                      ))
                    )}
                    <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                      <label className="button-secondary" style={{ cursor: 'pointer', textAlign: 'center', flex: 1 }}>
                        {fazendoUpload ? 'Enviando...' : '+ Anexar Orçamento'}
                        <input type="file" style={{ display: 'none' }} onChange={e => fazerUploadAnexo(e, 'Orçamento')} disabled={fazendoUpload} accept=".pdf,.png,.jpg,.jpeg" />
                      </label>
                      <label className="button-primary" style={{ cursor: 'pointer', textAlign: 'center', flex: 1, backgroundColor: '#10b981', borderColor: '#10b981' }}>
                        {fazendoUpload ? 'Enviando...' : '+ Anexar Nota Fiscal / Comprovante'}
                        <input type="file" style={{ display: 'none' }} onChange={e => fazerUploadAnexo(e, 'Nota Fiscal / Comprovante')} disabled={fazendoUpload} accept=".pdf,.png,.jpg,.jpeg" />
                      </label>
                    </div>
                  </div>
                </div>

                <div className="detail-section" style={{ marginTop: '24px' }}>
                  <div className="section-title-row"><div><span className="eyebrow">RASTREABILIDADE</span><h4>Histórico</h4></div></div>
                  <div className="timeline">
                    {historicoSolicitacao.map(evento => (
                      <div className="timeline-item" key={evento.id}>
                        <div className="timeline-date">{formatarDataHora(evento.data)}</div>
                        <div className="timeline-content"><strong>{evento.acao}</strong><span className="timeline-user">{evento.responsavel}</span></div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="modal-actions">
                {!ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Aprovação pendente' && (<><button className="button-primary" onClick={() => editarSolicitacao(solicitacaoSelecionada)}>Corrigir Pedido</button><button className="button-danger" style={{ marginLeft: 'auto' }} onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Pedido</button></>)}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Aprovação pendente' && (<><button className="button-primary" onClick={() => aprovarSolicitacao(solicitacaoSelecionada)}>Aprovar Solicitação</button><button className="button-danger" style={{ marginLeft: 'auto' }} onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button></>)}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Aprovada' && (<><button className="button-primary" onClick={() => iniciarExecucao(solicitacaoSelecionada)}>▶ Executar Solicitação</button><button className="button-danger" style={{ marginLeft: 'auto' }} onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button></>)}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Em execução' && (<><button className="button-primary" style={{ backgroundColor: '#10b981', borderColor: '#10b981' }} onClick={() => finalizarSolicitacao(solicitacaoSelecionada)}>✓ Finalizar Solicitação</button><button className="button-danger" style={{ marginLeft: 'auto' }} onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button></>)}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Finalizada' && (<div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><span style={{ fontSize: '13px', fontWeight: '600', color: '#059669' }}>✓ Solicitação finalizada</span><button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button></div>)}
              </div>
            </div>
          </div>
        )}

        {/* MODAL: NOVA SOLICITAÇÃO / EDIÇÃO */}
        {mostrarFormulario && (
          <div className="modal-overlay" style={{ zIndex: 500 }} onClick={e => { if (e.target === e.currentTarget) fecharFormulario() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{solicitacaoEditando ? 'EDIÇÃO' : 'NOVA SOLICITAÇÃO'}</span><h3>{solicitacaoEditando ? 'Editar solicitação' : 'Criar Solicitação'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormulario}>×</button>
              </div>
              <form className="form" onSubmit={salvarSolicitacao}>
                <div className="form-grid">
                  
                  <div className="form-group full">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><label style={{ margin: 0 }}>Condomínio *</label><button type="button" className="text-button" style={{ fontSize: '12px', padding: 0 }} onClick={e => { e.preventDefault(); e.stopPropagation(); abrirFormularioNovoCondominio() }}>+ Novo</button></div>
                    <select value={formulario.condominio} onChange={e => atualizarCampoFormulario('condominio', e.target.value)} required>
                      <option value="">Selecione...</option>
                      {condominios.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                    </select>
                  </div>
                  
                  <div className="form-group full">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><label style={{ margin: 0 }}>Categoria da Despesa *</label><button type="button" className="text-button" style={{ fontSize: '12px', padding: 0 }} onClick={e => { e.preventDefault(); e.stopPropagation(); abrirFormularioNovoCategoria() }}>+ Nova</button></div>
                    <select value={formulario.categoria} onChange={e => atualizarCampoFormulario('categoria', e.target.value)} required>
                      <option value="">Selecione...</option>
                      {categorias.map(cat => (<option key={cat.id} value={cat.nome}>{cat.nome}</option>))}
                    </select>
                  </div>

                  <div className="form-group full">
                    <label>O que está sendo comprado? *</label>
                    <input type="text" placeholder="Ex: Reforma da guarita..." value={formulario.descricao} onChange={e => atualizarCampoFormulario('descricao', e.target.value)} required />
                  </div>
                  
                  <div className="form-group">
                    <label>Valor de Serviço (R$)</label>
                    <input type="text" placeholder="Ex: 500,00" value={formulario.valor_servico} onChange={e => atualizarCampoFormulario('valor_servico', e.target.value)} />
                  </div>
                  
                  <div className="form-group">
                    <label>Valor de Produto / Material (R$)</label>
                    <input type="text" placeholder="Ex: 1200,00" value={formulario.valor_produto} onChange={e => atualizarCampoFormulario('valor_produto', e.target.value)} />
                  </div>
                  
                  <div className="form-group full">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><label style={{ margin: 0 }}>Fornecedor / Prestador de Serviço *</label><button type="button" className="text-button" style={{ fontSize: '12px', padding: 0 }} onClick={e => { e.preventDefault(); e.stopPropagation(); abrirFormularioNovoFornecedor() }}>+ Novo</button></div>
                    <select value={formulario.fornecedor} onChange={e => atualizarCampoFormulario('fornecedor', e.target.value)} required>
                      <option value="">Selecione...</option>
                      {fornecedores.map(forn => (<option key={forn.id || forn.nome} value={forn.nome}>{forn.nome}</option>))}
                    </select>
                  </div>

                  <div className="form-group full">
                    <label>Observação adicional *</label>
                    <textarea rows="3" placeholder="Informações úteis para a controladoria..." value={formulario.observacao} onChange={e => atualizarCampoFormulario('observacao', e.target.value)} required />
                  </div>
                </div>
                <div className="form-footer">
                  <div style={{ marginRight: 'auto', display: 'flex', alignItems: 'center' }}><span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Total estimado: </span><strong style={{ fontSize: '18px', marginLeft: '8px', color: 'var(--text-primary)' }}>{formatarValor(numero(formulario.valor_servico) + numero(formulario.valor_produto))}</strong></div>
                  <button type="button" className="button-secondary" onClick={fecharFormulario}>Cancelar</button>
                  <button type="submit" className="button-primary" disabled={salvando}>{salvando ? 'Enviando...' : 'Enviar Solicitação'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: NOVO CONDÔMINIO */}
        {mostrarFormularioCondominio && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioCondominio() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{condominioEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{condominioEditando ? 'Editar Condomínio' : 'Cadastrar Condomínio'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioCondominio}>×</button>
              </div>
              <form className="form" onSubmit={salvarCondominio}>
                <div className="form-grid">
                  <div className="form-group full">
                    <label>Nome do Condomínio *</label>
                    <input type="text" value={formularioCondominio.nome} onChange={e => atualizarCampoCondominio('nome', e.target.value)} required autoFocus />
                  </div>
                  <div className="form-group">
                    <label>CNPJ</label>
                    <input type="text" value={formularioCondominio.cnpj} onChange={e => atualizarCampoCondominio('cnpj', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Código Interno</label>
                    <input type="text" value={formularioCondominio.codigo} onChange={e => atualizarCampoCondominio('codigo', e.target.value)} />
                  </div>
                </div>
                <div className="form-footer">
                  <button type="button" className="button-secondary" onClick={fecharFormularioCondominio} disabled={salvando}>Cancelar</button>
                  <button type="submit" className="button-primary" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: NOVA CATEGORIA (COM LISTA DE LIMITES) */}
        {mostrarFormularioCategoria && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioCategoria() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{categoriaEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{categoriaEditando ? 'Editar Categoria' : 'Cadastrar Categoria'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioCategoria}>×</button>
              </div>
              <form className="form" onSubmit={salvarCategoria}>
                <div className="form-grid">
                  <div className="form-group full">
                    <label>Nome da Categoria *</label>
                    <input type="text" value={formularioCategoria.nome} onChange={e => atualizarCampoCategoria('nome', e.target.value)} required autoFocus placeholder="Ex: Limpeza, Manutenção..." />
                  </div>
                  <div className="form-group full">
                    <label>Descrição Breve</label>
                    <input type="text" value={formularioCategoria.descricao} onChange={e => atualizarCampoCategoria('descricao', e.target.value)} />
                  </div>

                  <div className="form-group full" style={{ marginTop: '8px' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Limites de Aprovação Automática por Condomínio</span>
                    </label>
                    
                    {condominios.length === 0 ? (
                      <div style={{ fontSize: '13px', color: '#64748b', padding: '12px', background: '#f8fafc', borderRadius: '8px', border: '1px dashed #cbd5e1', textAlign: 'center' }}>
                        Cadastre condomínios primeiro para definir limites de aprovação automática.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px', maxHeight: '200px', overflowY: 'auto', paddingRight: '4px' }}>
                        {condominios.map(c => (
                          <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                            <span style={{ fontSize: '14px', fontWeight: '600', color: '#334155' }}>{c.nome}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '13px', color: '#64748b' }}>R$</span>
                              <input 
                                type="text" 
                                style={{ width: '110px', padding: '8px', fontSize: '14px', textAlign: 'right', border: '1px solid #cbd5e1', borderRadius: '6px' }} 
                                placeholder="0,00"
                                value={formularioCategoria.limites[c.nome] || ''}
                                onChange={e => {
                                  setFormularioCategoria(prev => ({
                                    ...prev,
                                    limites: {
                                      ...prev.limites,
                                      [c.nome]: e.target.value
                                    }
                                  }))
                                }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="form-footer">
                  <button type="button" className="button-secondary" onClick={fecharFormularioCategoria} disabled={salvando}>Cancelar</button>
                  <button type="submit" className="button-primary" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: NOVO FORNECEDOR */}
        {mostrarFormularioFornecedor && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioFornecedor() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{fornecedorEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{fornecedorEditando ? 'Editar Fornecedor' : 'Cadastrar Fornecedor'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioFornecedor}>×</button>
              </div>
              <form className="form" onSubmit={salvarFornecedor}>
                <div className="form-grid">
                  <div className="form-group full">
                    <label>Nome / Razão Social *</label>
                    <input type="text" placeholder="Nome do fornecedor..." value={formularioFornecedor.nome} onChange={e => atualizarCampoFornecedor('nome', e.target.value)} required autoFocus />
                  </div>
                  <div className="form-group">
                    <label>CNPJ</label>
                    <input type="text" value={formularioFornecedor.cnpj} onChange={e => atualizarCampoFornecedor('cnpj', e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Categoria de Serviço</label>
                    <input type="text" value={formularioFornecedor.categoria} onChange={e => atualizarCampoFornecedor('categoria', e.target.value)} />
                  </div>
                </div>
                <div className="form-footer">
                  <button type="button" className="button-secondary" onClick={fecharFormularioFornecedor} disabled={salvando}>Cancelar</button>
                  <button type="submit" className="button-primary" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

      </main>
    </div>
  )
}

export default App