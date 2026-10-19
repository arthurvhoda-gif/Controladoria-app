import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer
} from 'recharts'
import XLSX from 'xlsx-js-style'
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
  const [sidebarAberta, setSidebarAberta] = useState(false)

  const [backendOnline, setBackendOnline] = useState(false)
  const [solicitacoes, setSolicitacoes] = useState([])
  const [condominios, setCondominios] = useState([])
  const [fornecedores, setFornecedores] = useState([])
  const [categorias, setCategorias] = useState([])

  // GESTÃO DE UNIDADES E RATEIO POR FRAÇÃO
  const [condominioUnidades, setCondominioUnidades] = useState(null)
  const [listaUnidades, setListaUnidades] = useState([])
  const [carregandoUnidades, setCarregandoUnidades] = useState(false)
  const [novaUnidade, setNovaUnidade] = useState({ identificacao: '', fracao_ideal: '' })
  const [rateioDados, setRateioDados] = useState(null)
  const [carregandoRateio, setCarregandoRateio] = useState(false)

  // NOTIFICAÇÕES E ALERTAS
  const [mostrarMenuNotificacoes, setMostrarMenuNotificacoes] = useState(false)
  const [notificacoesPushAtivas, setNotificacoesPushAtivas] = useState(false)

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

  const [filtroDataInicio, setFiltroDataInicio] = useState('')
  const [filtroDataFim, setFiltroDataFim] = useState('')
  const [filtroCondominioAnalise, setFiltroCondominioAnalise] = useState('todos')

  const [formulario, setFormulario] = useState({
    condominio: '', categoria: '', fornecedor: '', descricao: '',
    valor_servico: '', valor_produto: '', observacao: ''
  })

  const [formularioCondominio, setFormularioCondominio] = useState({ nome: '', cnpj: '', codigo: '' })
  const [formularioFornecedor, setFormularioFornecedor] = useState({ nome: '', cnpj: '', categoria: '' })
  const [formularioCategoria, setFormularioCategoria] = useState({ nome: '', descricao: '', limites: {} })

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

  useEffect(() => {
    if ('Notification' in window) {
      if (Notification.permission === 'granted') {
        setNotificacoesPushAtivas(true)
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') setNotificacoesPushAtivas(true)
        })
      }
    }
  }, [])

  function dispararNotificacaoNativa(titulo, corpo) {
    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(titulo, { body: corpo, icon: '/logo.png' })
      } catch (e) { }
    }
  }

  async function fazerLogin(e) {
    e.preventDefault()
    setCarregandoLogin(true)
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailLogin.trim().toLowerCase(), senha: senhaLogin })
      })
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
    } catch (err) {
      mostrarToast(err.message, 'error')
    } finally {
      setCarregandoLogin(false)
    }
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

  function confirmarAcao(titulo, mensagem, onConfirm, isDanger = false) {
    setDialog({ isOpen: true, type: 'confirm', title: titulo, message: mensagem, inputValue: '', confirmText: 'Sim, confirmar', cancelText: 'Cancelar', isDanger, onConfirm })
  }

  function pedirInput(titulo, mensagem, valorPadrao, onConfirm, isDanger = false) {
    setDialog({ isOpen: true, type: 'prompt', title: titulo, message: mensagem, inputValue: valorPadrao || '', confirmText: 'Salvar', cancelText: 'Cancelar', isDanger, onConfirm })
  }

  function fecharDialog() {
    setDialog(prev => ({ ...prev, isOpen: false, inputValue: '' }))
  }

  function handleConfirmDialog() {
    if (dialog.onConfirm) {
      dialog.type === 'prompt' ? dialog.onConfirm(dialog.inputValue) : dialog.onConfirm()
    }
    fecharDialog()
  }

  async function verificarBackend() {
    try {
      const resposta = await fetch(`${API_URL}/status`)
      setBackendOnline(resposta.ok)
    } catch {
      setBackendOnline(false)
    }
  }

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
        if (usuarioLogado.perfil === 'Solicitante') {
          dados = dados.filter(s => s.solicitante === usuarioLogado.nome)
        }
        
        const qtdAntiga = solicitacoes.length
        if (dados.length > qtdAntiga && qtdAntiga > 0) {
          dispararNotificacaoNativa('Nova Solicitação', 'Um novo pedido foi registrado no sistema.')
        }

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
  function formatarDataHora(dataStr) {
    if (!dataStr) return '-'
    try {
      const d = new Date(dataStr)
      return isNaN(d.getTime()) ? dataStr : d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch {
      return dataStr
    }
  }

  function normalizarTexto(v) {
    return String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
  }

  function textoStatus(status) {
    const n = normalizarTexto(status)
    if (n.includes('finalizada') || n.includes('finalizado')) return 'Finalizada'
    if (n.includes('em execucao') || n === 'execucao') return 'Em execução'
    if (n.includes('ajuste')) return 'Ajuste solicitado'
    if (n.includes('reprovada') || n.includes('reprovado')) return 'Reprovada'
    if (n.includes('aprovada') || n.includes('aprovado')) return 'Aprovada'
    if (n.includes('em analise')) return 'Em análise'
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

    return (
      <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: '600', backgroundColor, color, display: 'inline-block' }}>
        {txt}
      </span>
    )
  }

  function classeVariacao(valor) { return numero(valor) > 0 ? 'positive' : numero(valor) < 0 ? 'negative' : 'neutral' }

  const quantidadePendentes = solicitacoes.filter(item => textoStatus(item.status) === 'Aprovação pendente').length
  const valorTotalSolicitado = solicitacoes.reduce((total, item) => total + solicitado(item), 0)
  const valorTotalAprovado = solicitacoes.reduce((total, item) => ['Aprovada', 'Em execução', 'Finalizada'].includes(textoStatus(item.status)) ? total + (aprovado(item) || solicitado(item)) : total, 0)
  const valorTotalRealizado = solicitacoes.reduce((total, item) => textoStatus(item.status) === 'Finalizada' ? total + (realizado(item) || aprovado(item) || solicitado(item)) : total, 0)
  
  const economiaTotal = solicitacoes.reduce((total, item) => {
    if (textoStatus(item.status) === 'Finalizada') {
      const vSol = solicitado(item)
      const vReal = realizado(item) || aprovado(item) || vSol
      return total + (vSol - vReal)
    }
    return total
  }, 0)

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

  const solicitacoesAnaliseFiltradas = solicitacoes.filter(sol => {
    const nomeCondominio = sol.condominio || ''
    const matchCondominio = filtroCondominioAnalise === 'todos' || nomeCondominio === filtroCondominioAnalise
    
    let matchData = true
    if (sol.data && typeof sol.data === 'string') {
      const dataSol = sol.data.substring(0, 10)
      if (filtroDataInicio && dataSol < filtroDataInicio) matchData = false
      if (filtroDataFim && dataSol > filtroDataFim) matchData = false
    } else if ((filtroDataInicio || filtroDataFim) && !sol.data) {
      matchData = false
    }

    return matchCondominio && matchData
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
    if (!acc[cond]) acc[cond] = { aprovado: 0, realizado: 0, qtdSolicitacoes: 0 }
    acc[cond].qtdSolicitacoes += 1
    const statusAtual = textoStatus(sol.status)
    if (['Aprovada', 'Em execução', 'Finalizada'].includes(statusAtual)) acc[cond].aprovado += aprovado(sol) || solicitado(sol)
    if (statusAtual === 'Finalizada') acc[cond].realizado += realizado(sol) || aprovado(sol) || solicitado(sol)
    return acc
  }, {})

  const listaOrcamentoCondominio = Object.entries(orcamentoPorCondominio).map(([nome, d]) => ({ nome, ...d, saldo: d.aprovado - d.realizado })).sort((a, b) => b.aprovado - a.aprovado)

  // =========================================================================
  // GESTÃO DE UNIDADES E RATEIO
  // =========================================================================
  async function abrirGerenciadorUnidades(cond) {
    setCondominioUnidades(cond)
    setCarregandoUnidades(true)
    setNovaUnidade({ identificacao: '', fracao_ideal: '' })
    try {
      const res = await fetch(`${API_URL}/condominios/${cond.id}/unidades`, { headers: getAuthHeaders() })
      if (res.ok) {
        setListaUnidades(await res.json())
      } else {
        setListaUnidades([])
      }
    } catch {
      setListaUnidades([])
    } finally {
      setCarregandoUnidades(false)
    }
  }

  async function salvarNovaUnidade(e) {
    e.preventDefault()
    if (!novaUnidade.identificacao.trim()) {
      mostrarToast('Informe o número ou identificação da unidade.', 'error')
      return
    }
    const fracao = numero(novaUnidade.fracao_ideal)
    if (fracao <= 0) {
      mostrarToast('A fração ideal deve ser maior que zero.', 'error')
      return
    }

    try {
      const res = await fetch(`${API_URL}/condominios/${condominioUnidades.id}/unidades`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ identificacao: novaUnidade.identificacao.trim(), fracao_ideal: fracao })
      })
      if (!res.ok) {
        const err = await extrairErro(res, 'Erro ao cadastrar unidade.')
        throw new Error(err)
      }
      const criada = await res.json()
      setListaUnidades(prev => [...prev, criada])
      setNovaUnidade({ identificacao: '', fracao_ideal: '' })
      mostrarToast('Unidade cadastrada!', 'success')
    } catch (e) {
      mostrarToast(e.message, 'error')
    }
  }

  async function excluirUnidade(unidadeId) {
    confirmarAcao('Excluir Unidade', 'Deseja excluir esta unidade e sua respectiva fração?', async () => {
      try {
        const res = await fetch(`${API_URL}/unidades/${unidadeId}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error('Erro ao excluir unidade.')
        setListaUnidades(prev => prev.filter(u => u.id !== unidadeId))
        mostrarToast('Unidade removida com sucesso.', 'success')
      } catch (e) {
        mostrarToast(e.message, 'error')
      }
    }, true)
  }

  async function calcularRateioCondominio(condominioNome) {
    const condObj = condominios.find(c => c.nome === condominioNome)
    if (!condObj) {
      setRateioDados(null)
      return
    }
    setCarregandoRateio(true)
    try {
      const mesParam = filtroDataInicio ? `?mes=${filtroDataInicio.substring(0, 7)}` : ''
      const res = await fetch(`${API_URL}/condominios/${condObj.id}/rateio${mesParam}`, { headers: getAuthHeaders() })
      if (res.ok) {
        const dados = await res.json()
        setRateioDados(dados)
      } else {
        setRateioDados(null)
      }
    } catch {
      setRateioDados(null)
    } finally {
      setCarregandoRateio(false)
    }
  }

  useEffect(() => {
    if (pagina === 'analises' && filtroCondominioAnalise !== 'todos') {
      calcularRateioCondominio(filtroCondominioAnalise)
    } else {
      setRateioDados(null)
    }
  }, [filtroCondominioAnalise, filtroDataInicio, pagina, condominios])

  const somaFracaoTotal = listaUnidades.reduce((acc, u) => acc + numero(u.fracao_ideal), 0)

  // =========================================================================
  // EXPORTAÇÃO EXCEL (.XLSX)
  // =========================================================================
  function exportarRelatorioExcel() {
    if (solicitacoesAnaliseFiltradas.length === 0 && listaOrcamentoCondominio.length === 0) {
      mostrarToast('Não existem dados para exportar no filtro selecionado.', 'error')
      return
    }

    const wb = XLSX.utils.book_new()
    const periodoFormatado = filtroDataInicio || filtroDataFim ? `De ${filtroDataInicio ? new Date(filtroDataInicio + 'T00:00:00').toLocaleDateString('pt-BR') : 'Início'} até ${filtroDataFim ? new Date(filtroDataFim + 'T00:00:00').toLocaleDateString('pt-BR') : 'Hoje'}` : 'Todo o Período'
    const condFormatado = filtroCondominioAnalise === 'todos' ? 'Todos os Condomínios' : filtroCondominioAnalise
    const dataEmissao = new Date().toLocaleString('pt-BR')

    const bordaPadrao = { top: { style: 'thin', color: { rgb: 'CBD5E1' } }, bottom: { style: 'thin', color: { rgb: 'CBD5E1' } }, left: { style: 'thin', color: { rgb: 'CBD5E1' } }, right: { style: 'thin', color: { rgb: 'CBD5E1' } } }
    const bordaTotal = { top: { style: 'medium', color: { rgb: '0F172A' } }, bottom: { style: 'double', color: { rgb: '0F172A' } }, left: { style: 'thin', color: { rgb: 'CBD5E1' } }, right: { style: 'thin', color: { rgb: 'CBD5E1' } } }

    const estiloTitulo = { font: { name: 'Calibri', sz: 14, bold: true, color: { rgb: 'FFFFFF' } }, fill: { fgColor: { rgb: '0F172A' } }, alignment: { vertical: 'center', horizontal: 'left' } }
    const estiloSubtitulo = { font: { name: 'Calibri', sz: 10, italic: true, color: { rgb: '334155' } }, fill: { fgColor: { rgb: 'F1F5F9' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao }
    const estiloCabecalhoTabela = { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: 'FFFFFF' } }, fill: { fgColor: { rgb: '1E293B' } }, alignment: { vertical: 'center', horizontal: 'center', wrapText: true }, border: bordaPadrao }
    const formatoMoeda = '"R$" #,##0.00'

    // ABA 1: RESUMO POR CONDOMÍNIO
    const totalQtdResumo = listaOrcamentoCondominio.reduce((acc, i) => acc + (i.qtdSolicitacoes || 0), 0)
    const totalTeto = listaOrcamentoCondominio.reduce((acc, i) => acc + i.aprovado, 0)
    const totalRealizado = listaOrcamentoCondominio.reduce((acc, i) => acc + i.realizado, 0)
    const totalSaldo = totalTeto - totalRealizado

    const linhasResumo = [
      [{ v: 'HAIZE SÍNDICO PROFISSIONAL — RESUMO EXECUTIVO POR CONDOMÍNIO', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }],
      [{ v: `Condomínio: ${condFormatado}   |   Período: ${periodoFormatado}   |   Emitido em: ${dataEmissao}`, s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }],
      [],
      [
        { v: 'Condomínio', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Qtd Solicitações', s: estiloCabecalhoTabela },
        { v: 'Teto Aprovado (R$)', s: estiloCabecalhoTabela },
        { v: 'Gasto Realizado (R$)', s: estiloCabecalhoTabela },
        { v: 'Saldo Orçamentário (R$)', s: estiloCabecalhoTabela },
        { v: 'Status Orçamentário', s: estiloCabecalhoTabela }
      ]
    ]

    listaOrcamentoCondominio.forEach((item, idx) => {
      const corZebra = idx % 2 === 0 ? 'FFFFFF' : 'F8FAFC'
      let estado = 'No Limite'; let bgStatus = 'F1F5F9'; let corStatus = '475569'
      if (item.saldo > 0) { estado = 'Economia'; bgStatus = 'D1FAE5'; corStatus = '065F46' }
      if (item.saldo < 0) { estado = 'Estourado'; bgStatus = 'FEE2E2'; corStatus = '991B1B' }
      if (item.aprovado === 0) { estado = 'Sem Orçamento'; bgStatus = 'F1F5F9'; corStatus = '64748B' }
      const corSaldo = item.saldo < 0 ? 'DC2626' : '059669'

      linhasResumo.push([
        { v: item.nome, t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: item.qtdSolicitacoes || 0, t: 'n', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '334155' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } },
        { v: Number(item.aprovado.toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '1E293B' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number(item.realizado.toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '1E293B' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number(item.saldo.toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: corSaldo } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: estado, t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: corStatus } }, fill: { fgColor: { rgb: bgStatus } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } }
      ])
    })

    const ultimaLinhaDadosResumo = 4 + listaOrcamentoCondominio.length
    const bgTotalSaldoResumo = totalSaldo < 0 ? 'FEE2E2' : 'D1FAE5'
    const corTotalSaldoResumo = totalSaldo < 0 ? '991B1B' : '065F46'

    linhasResumo.push([
      { v: 'TOTAL CONSOLIDADO', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaTotal } },
      { t: 'n', f: `SUM(B5:B${ultimaLinhaDadosResumo})`, v: totalQtdResumo, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { t: 'n', f: `SUM(C5:C${ultimaLinhaDadosResumo})`, v: Number(totalTeto.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(D5:D${ultimaLinhaDadosResumo})`, v: Number(totalRealizado.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(E5:E${ultimaLinhaDadosResumo})`, v: Number(totalSaldo.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: corTotalSaldoResumo } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { v: totalSaldo >= 0 ? 'SALDO POSITIVO' : 'ORÇAMENTO ESTOURADO', t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: corTotalSaldoResumo } }, fill: { fgColor: { rgb: bgTotalSaldoResumo } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } }
    ])

    const wsResumo = XLSX.utils.aoa_to_sheet(linhasResumo)
    wsResumo['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 5 } }, { s: { r: 1, c: 0 }, e: { r: 1, c: 5 } }]
    wsResumo['!cols'] = [{ wch: 32 }, { wch: 18 }, { wch: 22 }, { wch: 22 }, { wch: 24 }, { wch: 22 }]
    XLSX.utils.book_append_sheet(wb, wsResumo, 'Resumo por Condomínio')

    // ABA 2: EXTRATO DE SOLICITAÇÕES
    const totalSol = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + solicitado(s), 0)
    const totalApr = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + (aprovado(s) || solicitado(s)), 0)
    const totalReal = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + (realizado(s) || 0), 0)
    const qtdPedidos = solicitacoesAnaliseFiltradas.length

    const linhasExtrato = [
      [{ v: 'HAIZE SÍNDICO PROFISSIONAL — EXTRATO DETALHADO DE SOLICITAÇÕES', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }],
      [{ v: `Condomínio: ${condFormatado}   |   Período: ${periodoFormatado}   |   Total de Solicitações: ${qtdPedidos}   |   Emitido em: ${dataEmissao}`, s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }],
      [],
      [
        { v: 'Código', s: estiloCabecalhoTabela },
        { v: 'Condomínio', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Categoria', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Descrição do Pedido', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Fornecedor', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Valor Solicitado (R$)', s: estiloCabecalhoTabela },
        { v: 'Valor Aprovado (R$)', s: estiloCabecalhoTabela },
        { v: 'Valor Realizado (R$)', s: estiloCabecalhoTabela },
        { v: 'Status', s: estiloCabecalhoTabela },
        { v: 'Data de Abertura', s: estiloCabecalhoTabela }
      ]
    ]

    solicitacoesAnaliseFiltradas.forEach((s, idx) => {
      const corZebra = idx % 2 === 0 ? 'FFFFFF' : 'F8FAFC'
      const st = textoStatus(s.status)
      let bgSt = 'FEF3C7'; let corSt = 'D97706'
      if (st === 'Aprovada') { bgSt = 'DBEAFE'; corSt = '1D4ED8' }
      if (st === 'Em execução') { bgSt = 'E0E7FF'; corSt = '4338CA' }
      if (st === 'Finalizada') { bgSt = 'D1FAE5'; corSt = '065F46' }
      if (st === 'Reprovada') { bgSt = 'FEE2E2'; corSt = '991B1B' }

      linhasExtrato.push([
        { v: s.numero || '', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '2563EB' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } },
        { v: s.condominio || '', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: s.categoria || '-', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '6B21A8' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: s.descricao || '', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '334155' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: s.fornecedor || '-', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '475569' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: Number(solicitado(s).toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '334155' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number((aprovado(s) || solicitado(s)).toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '1D4ED8' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number((realizado(s) || 0).toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '059669' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: st, t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: corSt } }, fill: { fgColor: { rgb: bgSt } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } },
        { v: formatarDataHora(s.data), t: 's', s: { font: { name: 'Calibri', sz: 10, color: { rgb: '64748B' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } }
      ])
    })

    const ultimaLinhaDadosExtrato = 4 + solicitacoesAnaliseFiltradas.length

    linhasExtrato.push([
      { v: 'TOTAL GASTOS', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { t: 'n', f: `COUNTA(A5:A${ultimaLinhaDadosExtrato})`, v: qtdPedidos, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '1D4ED8' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { v: 'solicitações no período', t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: '475569' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaTotal } },
      { v: `Soma consolidada automática (${qtdPedidos} pedidos)`, t: 's', s: { font: { name: 'Calibri', sz: 10, italic: true, color: { rgb: '475569' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaTotal } },
      { v: '-', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '64748B' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { t: 'n', f: `SUM(F5:F${ultimaLinhaDadosExtrato})`, v: Number(totalSol.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(G5:G${ultimaLinhaDadosExtrato})`, v: Number(totalApr.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '1D4ED8' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(H5:H${ultimaLinhaDadosExtrato})`, v: Number(totalReal.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '059669' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { v: `${qtdPedidos} itens`, t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { v: '-', t: 's', s: { font: { name: 'Calibri', sz: 10, color: { rgb: '64748B' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } }
    ])

    const wsExtrato = XLSX.utils.aoa_to_sheet(linhasExtrato)
    wsExtrato['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 9 } }, { s: { r: 1, c: 0 }, e: { r: 1, c: 9 } }]
    wsExtrato['!cols'] = [{ wch: 16 }, { wch: 24 }, { wch: 22 }, { wch: 38 }, { wch: 24 }, { wch: 22 }, { wch: 22 }, { wch: 22 }, { wch: 18 }, { wch: 20 }]
    XLSX.utils.book_append_sheet(wb, wsExtrato, 'Extrato de Solicitações')

    const nomeArquivo = `Relatorio_Controladoria_${filtroCondominioAnalise !== 'todos' ? filtroCondominioAnalise : 'Geral'}.xlsx`
    XLSX.writeFile(wb, nomeArquivo)
    mostrarToast('Relatório Executivo Excel (.xlsx) gerado com sucesso!', 'success')
  }

  function exportarRelatorioPDF() {
    if (solicitacoesAnaliseFiltradas.length === 0 && listaOrcamentoCondominio.length === 0) {
      mostrarToast('Não existem dados para exportar no filtro selecionado.', 'error')
      return
    }

    const periodoFormatado = filtroDataInicio || filtroDataFim ? `De ${filtroDataInicio ? new Date(filtroDataInicio + 'T00:00:00').toLocaleDateString('pt-BR') : 'Início'} até ${filtroDataFim ? new Date(filtroDataFim + 'T00:00:00').toLocaleDateString('pt-BR') : 'Hoje'}` : 'Todo o Período'
    const condFormatado = filtroCondominioAnalise === 'todos' ? 'Todos os Condomínios' : filtroCondominioAnalise

    const totalQtd = listaOrcamentoCondominio.reduce((acc, i) => acc + (i.qtdSolicitacoes || 0), 0)
    const totalTeto = listaOrcamentoCondominio.reduce((acc, i) => acc + i.aprovado, 0)
    const totalRealizado = listaOrcamentoCondominio.reduce((acc, i) => acc + i.realizado, 0)
    const totalSaldo = totalTeto - totalRealizado

    const totalSol = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + solicitado(s), 0)
    const totalReal = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + (s.valor_realizado || s.valor_aprovado || s.valor), 0)

    const janela = window.open('', '_blank')
    if (!janela) {
      mostrarToast('Permita pop-ups no navegador para gerar o PDF.', 'error')
      return
    }

    const linhasResumo = listaOrcamentoCondominio.map(item => `
      <tr>
        <td style="padding: 8px; border: 1px solid #cbd5e1; font-weight: bold;">${item.nome}</td>
        <td style="padding: 8px; border: 1px solid #cbd5e1; text-align: center; font-weight: 600;">${item.qtdSolicitacoes || 0}</td>
        <td style="padding: 8px; border: 1px solid #cbd5e1; text-align: right;">${formatarValor(item.aprovado)}</td>
        <td style="padding: 8px; border: 1px solid #cbd5e1; text-align: right;">${formatarValor(item.realizado)}</td>
        <td style="padding: 8px; border: 1px solid #cbd5e1; text-align: right; color: ${item.saldo < 0 ? '#dc2626' : '#059669'}; font-weight: bold;">${formatarValor(item.saldo)}</td>
      </tr>
    `).join('')

    const linhasSols = solicitacoesAnaliseFiltradas.map(s => `
      <tr>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; font-family: monospace;">${s.numero || ''}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0;">${s.condominio || ''}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0;">${s.categoria || '-'}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0;">${s.descricao || ''}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; text-align: right;">${formatarValor(s.valor)}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; text-align: right;">${formatarValor(s.valor_realizado || s.valor_aprovado || s.valor)}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: 600;">${textoStatus(s.status)}</td>
      </tr>
    `).join('')

    janela.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Relatório de Fecho - Controladoria Haize</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 30px; color: #0f172a; margin: 0; }
          .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 16px; margin-bottom: 24px; }
          .title { font-size: 22px; font-weight: 800; }
          .subtitle { font-size: 13px; color: #64748b; margin-top: 4px; }
          .meta { font-size: 12px; color: #334155; }
          h3 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.5px; margin: 24px 0 10px 0; color: #1e293b; }
          table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 20px; }
          th { background-color: #f1f5f9; padding: 8px; border: 1px solid #cbd5e1; text-align: left; font-weight: 700; }
          tfoot td { background-color: #f8fafc; font-weight: 800; border: 1px solid #cbd5e1; padding: 8px; }
          @media print {
            body { padding: 15px; }
            button { display: none; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <div>
            <div class="title">HAIZE SÍNDICO PROFISSIONAL</div>
            <div class="subtitle">Relatório Consolidado de Fecho Orçamentário e Compras</div>
          </div>
          <div class="meta" style="text-align: right;">
            <div><strong>Filtro:</strong> ${condFormatado}</div>
            <div><strong>Período:</strong> ${periodoFormatado}</div>
            <div><strong>Emissão:</strong> ${new Date().toLocaleDateString('pt-BR')}</div>
          </div>
        </div>

        <h3>Resumo por Condomínio</h3>
        <table>
          <thead>
            <tr>
              <th>Condomínio</th>
              <th style="text-align: center;">Qtd Solicitações</th>
              <th style="text-align: right;">Teto Aprovado</th>
              <th style="text-align: right;">Gasto Realizado</th>
              <th style="text-align: right;">Saldo</th>
            </tr>
          </thead>
          <tbody>${linhasResumo}</tbody>
          <tfoot>
            <tr>
              <td>TOTAL CONSOLIDADO</td>
              <td style="text-align: center;">${totalQtd}</td>
              <td style="text-align: right;">${formatarValor(totalTeto)}</td>
              <td style="text-align: right;">${formatarValor(totalRealizado)}</td>
              <td style="text-align: right; color: ${totalSaldo < 0 ? '#dc2626' : '#059669'};">${formatarValor(totalSaldo)}</td>
            </tr>
          </tfoot>
        </table>

        <h3>Extrato de Solicitações</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Condomínio</th>
              <th>Categoria</th>
              <th>Descrição</th>
              <th style="text-align: right;">Solicitado</th>
              <th style="text-align: right;">Final/Realizado</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>${linhasSols}</tbody>
          <tfoot>
            <tr>
              <td colspan="4">TOTAL GASTOS (${solicitacoesAnaliseFiltradas.length} solicitações no período)</td>
              <td style="text-align: right;">${formatarValor(totalSol)}</td>
              <td style="text-align: right;">${formatarValor(totalReal)}</td>
              <td>-</td>
            </tr>
          </tfoot>
        </table>

        <script>
          window.onload = function() { window.print(); }
        </script>
      </body>
      </html>
    `)
    janela.document.close()
  }

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
    if (!formulario.condominio || !formulario.categoria || !formulario.fornecedor || !formulario.descricao || !formulario.observacao) {
      mostrarToast('Por favor, preencha todos os campos obrigatórios (*).', 'error')
      return
    }
    const vServ = numero(formulario.valor_servico)
    const vProd = numero(formulario.valor_produto)
    if (vServ <= 0 && vProd <= 0) {
      mostrarToast('O valor total (Serviço ou Produto) deve ser maior que zero.', 'error')
      return
    }

    const condObj = condominios.find(c => c.nome === formulario.condominio)
    const payload = {
      ...formulario,
      condominio_id: condObj?.id || null,
      valor_servico: vServ,
      valor_produto: vProd,
      solicitante: usuarioLogado.nome,
      status: 'Aprovação pendente'
    }

    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/solicitacoes${solicitacaoEditando ? `/${solicitacaoEditando.id}` : ''}`, {
        method: solicitacaoEditando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar solicitação.')
        throw new Error(erroMsg)
      }
      await carregarDados()
      fecharFormulario()
      mostrarToast(solicitacaoEditando ? 'Atualizada com sucesso!' : 'Enviada com sucesso!', 'success')
    } catch (erro) {
      mostrarToast(erro.message, 'error')
    } finally {
      setSalvando(false)
    }
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
    if (arquivo.size > 10 * 1024 * 1024) {
      mostrarToast('O arquivo deve ter no máximo 10MB', 'error')
      return
    }

    const formData = new FormData()
    formData.append('arquivo', arquivo)
    formData.append('tipo', tipoDocumento)
    formData.append('responsavel', usuarioLogado.nome)

    setFazendoUpload(true)
    try {
      const res = await fetch(`${API_URL}/solicitacoes/${solicitacaoSelecionada.id}/anexos`, {
        method: 'POST',
        headers: getAuthHeaders(true),
        body: formData
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao anexar arquivo.')
        throw new Error(erroMsg)
      }
      mostrarToast('Arquivo anexado com sucesso!', 'success')
      await abrirSolicitacao(solicitacaoSelecionada)
    } catch (e) {
      mostrarToast(e.message, 'error')
    } finally {
      setFazendoUpload(false)
    }
  }

  function aprovarSolicitacao(solicitacao) {
    pedirInput('Aprovar solicitação', 'Informe o valor aprovado para essa compra:', String(aprovado(solicitacao) || solicitado(solicitacao) || ''), async v => {
      const vNum = numero(v)
      if (vNum <= 0) { mostrarToast('O valor aprovado deve ser maior que zero.', 'error'); return }
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ status: 'Aprovada', valor_aprovado: vNum })
        })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao aprovar solicitação.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        dispararNotificacaoNativa('Solicitação Aprovada', `O pedido ${solicitacao.numero} foi aprovado.`)
        mostrarToast('Solicitação aprovada com sucesso.', 'success')
        fecharSolicitacao()
      } catch (e) { mostrarToast(e.message, 'error') }
    })
  }

  function solicitarAjuste(solicitacao) {
    pedirInput('Solicitar Ajuste', 'Informe o motivo ou o que precisa ser corrigido pelo solicitante:', solicitacao.motivo_ajuste || '', async motivo => {
      if (!motivo || !motivo.trim()) { mostrarToast('Informe o motivo do ajuste.', 'error'); return }
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ status: 'Ajuste solicitado', motivo_ajuste: motivo.trim() })
        })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao solicitar ajuste.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        dispararNotificacaoNativa('Ajuste Solicitado', `O pedido ${solicitacao.numero} requer correções.`)
        mostrarToast('Ajuste solicitado ao autor.', 'success')
        fecharSolicitacao()
      } catch (e) { mostrarToast(e.message, 'error') }
    })
  }

  function reprovarSolicitacao(solicitacao) {
    pedirInput('Reprovar Solicitação', 'Informe o motivo da reprovação:', '', async motivo => {
      if (!motivo || !motivo.trim()) { mostrarToast('Informe o motivo da reprovação.', 'error'); return }
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ status: 'Reprovada', motivo_ajuste: motivo.trim() })
        })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao reprovar solicitação.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        mostrarToast('Solicitação reprovada.', 'success')
        fecharSolicitacao()
      } catch (e) { mostrarToast(e.message, 'error') }
    }, true)
  }

  function iniciarExecucao(solicitacao) {
    confirmarAcao('Executar solicitação', `Deseja executar a solicitação ${solicitacao.numero || ''}?`, async () => {
      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/iniciar-execucao`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ observacao_execucao: '' })
        })
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
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/finalizar`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ valor_realizado: vNum })
        })
        if (!res.ok) {
          const erroMsg = await extrairErro(res, 'Erro ao finalizar solicitação.')
          throw new Error(erroMsg)
        }
        await carregarDados()
        dispararNotificacaoNativa('Solicitação Finalizada', `O pedido ${solicitacao.numero} foi concluído com sucesso.`)
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
        mostrarToast('Excluída com sucesso.', 'success')
      } catch (e) { mostrarToast(e.message, 'error') }
    }, true)
  }

  function fecharFormularioCondominio() { setMostrarFormularioCondominio(false); setCondominioEditando(null); setFormularioCondominio({ nome: '', cnpj: '', codigo: '' }) }
  function abrirFormularioNovoCondominio() { setCondominioEditando(null); setFormularioCondominio({ nome: '', cnpj: '', codigo: '' }); setMostrarFormularioCondominio(true) }
  function editarCondominio(cond) { setCondominioEditando(cond); setFormularioCondominio({ nome: cond.nome || '', cnpj: cond.cnpj || '', codigo: cond.codigo || '' }); setMostrarFormularioCondominio(true) }
  
  async function salvarCondominio(e) {
    e.preventDefault()
    if (!formularioCondominio.nome) return
    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/condominios${condominioEditando ? `/${condominioEditando.id}` : ''}`, {
        method: condominioEditando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(formularioCondominio)
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar condomínio.')
        throw new Error(erroMsg)
      }
      const salvo = await res.json()
      await carregarDados()
      fecharFormularioCondominio()
      if (mostrarFormulario && !condominioEditando) atualizarCampoFormulario('condominio', salvo.nome)
      mostrarToast('Condomínio salvo com sucesso!', 'success')
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
        method: categoriaEditando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar categoria.')
        throw new Error(erroMsg)
      }
      const salvo = await res.json()
      await carregarDados()
      fecharFormularioCategoria()
      if (mostrarFormulario && !categoriaEditando) atualizarCampoFormulario('categoria', salvo.nome)
      mostrarToast('Categoria salva!', 'success')
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
      const res = await fetch(`${API_URL}/fornecedores${fornecedorEditando ? `/${fornecedorEditando.id}` : ''}`, {
        method: fornecedorEditando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(formularioFornecedor)
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar fornecedor.')
        throw new Error(erroMsg)
      }
      const salvo = await res.json()
      await carregarDados()
      fecharFormularioFornecedor()
      if (mostrarFormulario && !fornecedorEditando) atualizarCampoFormulario('fornecedor', salvo.nome)
      mostrarToast('Fornecedor salvo com sucesso!', 'success')
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

  function atualizarCampoCondominio(campo, valor) { setFormularioCondominio(atual => ({ ...atual, [campo]: valor })) }
  function atualizarCampoCategoria(campo, valor) { setFormularioCategoria(atual => ({ ...atual, [campo]: valor })) }
  function atualizarCampoFornecedor(campo, valor) { setFormularioFornecedor(atual => ({ ...atual, [campo]: valor })) }

  if (!usuarioLogado) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', width: '100%', backgroundColor: '#f8fafc', backgroundImage: 'radial-gradient(circle at 50% -20%, #dbeafe, #f8fafc 60%)', padding: '20px', boxSizing: 'border-box' }}>
        <div className="toast-container">
          {toasts.map(t => (<div key={t.id} className={`toast ${t.tipo}`}><span className="toast-icon">{t.tipo === 'success' ? '✓' : '!'}</span><span>{t.mensagem}</span></div>))}
        </div>
        <div style={{ background: '#ffffff', padding: '40px', borderRadius: '16px', boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)', width: '100%', maxWidth: '420px', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <img src="/logo.png" alt="Haize Logo" style={{ width: '80px', height: '80px', marginBottom: '16px', borderRadius: '12px' }} onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='flex'; }} />
          <div style={{ display: 'none', width: '64px', height: '64px', background: 'linear-gradient(135deg, #3b82f6, #2563eb)', borderRadius: '16px', alignItems: 'center', justifyContent: 'center', fontSize: '32px', fontWeight: '800', color: 'white', margin: '0 0 24px 0' }}>C</div>
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
        <div className="dialog-overlay" onClick={e => { if (e.target === e.currentTarget) fecharDialog() }}>
          <div className="dialog-box">
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>{dialog.title}</h3>
            <p style={{ margin: 0, fontSize: '14px', color: '#475569' }}>{dialog.message}</p>
            {dialog.type === 'prompt' && (
              <input type="text" className="dialog-input" value={dialog.inputValue} onChange={e => setDialog(p => ({ ...p, inputValue: e.target.value }))} autoFocus onKeyDown={e => { if (e.key === 'Enter') handleConfirmDialog() }} />
            )}
            <div className="dialog-actions">
              <button type="button" className="button-secondary" onClick={fecharDialog}>{dialog.cancelText}</button>
              <button type="button" className={dialog.isDanger ? 'button-danger' : 'button-primary'} onClick={handleConfirmDialog}>{dialog.confirmText}</button>
            </div>
          </div>
        </div>
      )}

      {sidebarAberta && (
        <div className="sidebar-overlay" onClick={() => setSidebarAberta(false)} />
      )}

      <aside className={`sidebar ${sidebarAberta ? 'open' : ''}`}>
        <div className="brand">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img src="/logo.png" alt="Haize" style={{ width: '38px', height: '38px', borderRadius: '8px', backgroundColor: 'white', padding: '2px' }} onError={(e) => { e.target.style.display='none'; }} />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <strong style={{ fontSize: '18px', letterSpacing: '-0.5px' }}>Controladoria</strong>
              <span style={{ fontSize: '12px', opacity: 0.8 }}>Haize Síndico Profissional</span>
            </div>
          </div>
          <button onClick={() => setSidebarAberta(false)} className="fechar-menu-mobile">✕</button>
        </div>

        <nav className="sidebar-nav" style={{ flex: 1 }}>
          <button className={pagina === 'dashboard' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('dashboard'); setSidebarAberta(false); }}><span className="nav-icon">◈</span><span>Dashboard</span></button>
          <button className={pagina === 'analises' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('analises'); setSidebarAberta(false); }}><span className="nav-icon">◠</span><span>Análises</span></button>
          <button className={pagina === 'solicitacoes' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('solicitacoes'); setSidebarAberta(false); }}><span className="nav-icon">▣</span><span>Solicitações</span>{ehControladoria && quantidadePendentes > 0 && (<span className="nav-count">{quantidadePendentes}</span>)}</button>
          <button className={pagina === 'compras' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('compras'); setSidebarAberta(false); }}><span className="nav-icon">◫</span><span>Compras</span></button>
          
          <div style={{ margin: '16px 0 8px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }}></div>
          
          <button className={pagina === 'condominios' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('condominios'); setSidebarAberta(false); }}><span className="nav-icon">🏢</span><span>Condomínios</span></button>
          <button className={pagina === 'categorias' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('categorias'); setSidebarAberta(false); }}><span className="nav-icon">🏷️</span><span>Categorias</span></button>
          <button className={pagina === 'fornecedores' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('fornecedores'); setSidebarAberta(false); }}><span className="nav-icon">🤝</span><span>Fornecedores</span></button>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="icon-button menu-mobile-btn" onClick={() => setSidebarAberta(!sidebarAberta)}>☰</button>
            <div>
              <span className="breadcrumb">
                Controladoria {' / '} {pagina === 'dashboard' ? 'Dashboard' : pagina === 'solicitacoes' ? 'Solicitações' : pagina}
              </span>
              <h1>{pagina === 'dashboard' ? 'Visão geral' : pagina === 'solicitacoes' ? ehControladoria ? 'Aprovações' : 'Minhas Solicitações' : pagina.charAt(0).toUpperCase() + pagina.slice(1)}</h1>
            </div>
          </div>
          
          <div className="topbar-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* CENTRAL DE NOTIFICAÇÕES */}
            <div style={{ position: 'relative' }}>
              <button 
                className="icon-button" 
                onClick={() => setMostrarMenuNotificacoes(!mostrarMenuNotificacoes)}
                style={{ position: 'relative', width: '40px', height: '40px', borderRadius: '50%', background: '#f1f5f9', border: '1px solid #cbd5e1', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', fontSize: '18px' }}
                title="Central de Alertas e Notificações"
              >
                🔔
                {quantidadePendentes > 0 && (
                  <span style={{ position: 'absolute', top: '-4px', right: '-4px', background: '#ef4444', color: 'white', fontSize: '11px', fontWeight: 'bold', width: '18px', height: '18px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {quantidadePendentes}
                  </span>
                )}
              </button>

              {mostrarMenuNotificacoes && (
                <div style={{ position: 'absolute', right: 0, top: '48px', width: '320px', background: 'white', border: '1px solid #cbd5e1', borderRadius: '12px', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15)', zIndex: 9999, overflow: 'hidden' }}>
                  <div style={{ padding: '14px 16px', background: '#0f172a', color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '14px' }}>Central de Alertas</strong>
                    <span style={{ fontSize: '11px', background: '#334155', padding: '2px 8px', borderRadius: '999px' }}>{quantidadePendentes} pendentes</span>
                  </div>
                  <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                    {solicitacoes.filter(s => textoStatus(s.status) === 'Aprovação pendente').length === 0 ? (
                      <div style={{ padding: '24px', textAlign: 'center', fontSize: '13px', color: '#64748b' }}>Nenhuma solicitação pendente no momento. Tudo em dia!</div>
                    ) : (
                      solicitacoes.filter(s => textoStatus(s.status) === 'Aprovação pendente').map(s => (
                        <div key={s.id} onClick={() => { abrirSolicitacao(s); setMostrarMenuNotificacoes(false) }} style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <strong style={{ fontSize: '13px', color: '#0f172a' }}>{s.numero} • {s.condominio}</strong>
                            <span style={{ fontSize: '11px', color: '#d97706', fontWeight: '600' }}>{formatarValor(s.valor)}</span>
                          </div>
                          <span style={{ fontSize: '12px', color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.descricao}</span>
                        </div>
                      ))
                    )}
                  </div>
                  <div style={{ padding: '10px', background: '#f8fafc', textAlign: 'center', borderTop: '1px solid #e2e8f0' }}>
                    <span style={{ fontSize: '11px', color: notificacoesPushAtivas ? '#059669' : '#d97706', fontWeight: '600' }}>
                      {notificacoesPushAtivas ? '✓ Notificações Push ativas' : '⚠️ Notificações do navegador desativadas'}
                    </span>
                  </div>
                </div>
              )}
            </div>

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
              <div className="kpi-card highlight"><div className="kpi-top"><span>Economia (Finalizadas)</span><span className="kpi-icon success">↓</span></div><strong>{formatarValor(economiaTotal)}</strong></div>
            </section>

            <section className="dashboard-grid">
              <div className="panel">
                <div className="panel-header"><div><span className="eyebrow">DESTAQUES</span><h3>Maiores Solicitações</h3></div></div>
                <div className="table">
                  <div className="table-header"><span>ID</span><span>Condomínio</span><span>Descrição</span><span>Valor Total</span><span>Status</span></div>
                  {maioresSolicitacoes.slice(0, 5).map(sol => (
                    <div className="table-row clickable" key={sol.id} onClick={() => abrirSolicitacao(sol)}>
                      <span className="id">{sol.numero}</span>
                      <span>{sol.condominio}</span>
                      <span>{sol.descricao}</span>
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
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                <select value={filtroCondominioAnalise} onChange={e => setFiltroCondominioAnalise(e.target.value)} style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '8px', backgroundColor: '#fff', fontSize: '14px', color: 'var(--text-primary)', outline: 'none', cursor: 'pointer' }}>
                  <option value="todos">Todos os Condomínios</option>
                  {condominios?.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                </select>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#fff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '4px 10px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '600' }}>De:</span>
                  <input type="date" value={filtroDataInicio} onChange={e => setFiltroDataInicio(e.target.value)} style={{ border: 'none', outline: 'none', fontSize: '13px', background: 'transparent', color: 'var(--text-primary)', cursor: 'pointer' }} />
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '600', marginLeft: '4px' }}>Até:</span>
                  <input type="date" value={filtroDataFim} onChange={e => setFiltroDataFim(e.target.value)} style={{ border: 'none', outline: 'none', fontSize: '13px', background: 'transparent', color: 'var(--text-primary)', cursor: 'pointer' }} />
                  {(filtroDataInicio || filtroDataFim) && (
                    <button onClick={() => { setFiltroDataInicio(''); setFiltroDataFim('') }} style={{ border: 'none', background: '#f1f5f9', borderRadius: '4px', padding: '2px 6px', fontSize: '11px', cursor: 'pointer', color: '#64748b' }}>Limpar</button>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="button-secondary" onClick={exportarRelatorioExcel} style={{ padding: '8px 14px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>📊</span> Exportar Excel (.xlsx)
                  </button>
                  <button className="button-secondary" onClick={exportarRelatorioPDF} style={{ padding: '8px 14px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>🖨️</span> Imprimir / PDF
                  </button>
                </div>
              </div>
            </section>

            {/* PAINEL DE RATEIO POR FRAÇÃO IDEAL */}
            {filtroCondominioAnalise !== 'todos' && (
              <section className="dashboard-grid" style={{ marginTop: '24px' }}>
                <div className="panel" style={{ gridColumn: '1 / -1' }}>
                  <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span className="eyebrow">RATEIO AUTOMÁTICO</span>
                      <h3>Distribuição por Fração Ideal — {filtroCondominioAnalise}</h3>
                    </div>
                    {rateioDados && (
                      <span style={{ fontSize: '13px', fontWeight: '700', color: '#1d4ed8', background: '#eff6ff', padding: '6px 12px', borderRadius: '8px' }}>
                        Total das Despesas: {formatarValor(rateioDados.total_gasto_condominio)} ({rateioDados.quantidade_solicitacoes} despesas)
                      </span>
                    )}
                  </div>

                  {carregandoRateio ? (
                    <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Calculando rateio de despesas...</div>
                  ) : !rateioDados || rateioDados.rateio_unidades.length === 0 ? (
                    <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>
                      Nenhuma unidade/fração cadastrada para este condomínio. Vá na aba de <strong>Condomínios</strong> e clique em <strong>🏘️ Unidades</strong> para cadastrar.
                    </div>
                  ) : (
                    <div className="table">
                      <div className="table-header" style={{ gridTemplateColumns: '2fr 1fr 1fr' }}>
                        <span>Unidade / Apartamento</span>
                        <span>Fração Ideal (%)</span>
                        <span style={{ textAlign: 'right' }}>Valor a Pagar (R$)</span>
                      </div>
                      {rateioDados.rateio_unidades.map((u, i) => (
                        <div className="table-row" key={i} style={{ gridTemplateColumns: '2fr 1fr 1fr' }}>
                          <strong>{u.unidade}</strong>
                          <span style={{ color: '#475569', fontWeight: '600' }}>{formatarNumero(u.fracao_ideal)}%</span>
                          <strong style={{ textAlign: 'right', color: '#059669' }}>{formatarValor(u.valor_devido)}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            )}

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
                      <option value="Ajuste solicitado">Ajuste solicitado</option>
                      <option value="Aprovada">Aprovada</option>
                      <option value="Em execução">Em execução</option>
                      <option value="Finalizada">Finalizada</option>
                      <option value="Reprovada">Reprovada</option>
                    </select>
                  )}
                  <input style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '8px' }} type="text" placeholder="Buscar..." value={pagina === 'solicitacoes' ? filtroSolicitacao : filtroCompra} onChange={e => pagina === 'solicitacoes' ? setFiltroSolicitacao(e.target.value) : setFiltroCompra(e.target.value)} />
                </div>
              </div>
              <div className="table">
                <div className="table-header" style={pagina === 'compras' ? { gridTemplateColumns: '100px 1.2fr 2fr 1fr 1fr 120px' } : undefined}>
                  <span>ID</span><span>Condomínio</span><span>Descrição</span>{pagina === 'compras' && (<span>Solicitado</span>)}<span>{pagina === 'compras' ? 'Aprovado' : 'Total'}</span><span>Status</span>
                </div>
                {(pagina === 'solicitacoes' ? solicitacoesFiltradas : comprasFiltradas).map(sol => (
                  <div className="table-row clickable" key={sol.id} style={pagina === 'compras' ? { gridTemplateColumns: '100px 1.2fr 2fr 1fr 1fr 120px' } : undefined} onClick={() => abrirSolicitacao(sol)}>
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
                      {condominio.codigo && (<span className="company-detail">Código: {condominio.codigo}</span>)}
                      
                      <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '16px', paddingTop: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="text-button" style={{ color: '#2563eb', fontWeight: 'bold' }} onClick={() => abrirGerenciadorUnidades(condominio)}>🏘️ Unidades</button>
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

        {pagina === 'fornecedores' && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">CADASTRO</span><h3>Fornecedores</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoFornecedor}>+ Novo Fornecedor</button>
              </div>
              <div className="company-grid">
                {fornecedores.map(forn => {
                  const nome = forn.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.fornecedor === nome).length
                  return (
                    <div className="company-card" key={forn.id}>
                      <div className="company-card-top">
                        <div className="company-avatar" style={{ background: '#f1f5f9', color: '#475569' }}>{String(nome).charAt(0).toUpperCase()}</div>
                        <span className="badge neutral">Ativo</span>
                      </div>
                      <h4>{nome}</h4>
                      {forn.cnpj && (<span className="company-detail">CNPJ: {forn.cnpj}</span>)}
                      <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '16px', paddingTop: '16px', display: 'flex', justifyContent: 'space-between' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="text-button" onClick={() => editarFornecedor(forn)}>Editar</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirFornecedor(forn.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>
        )}

        {/* MODAL DE GERENCIAMENTO DE UNIDADES E FRAÇÕES */}
        {condominioUnidades && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) setCondominioUnidades(null) }}>
            <div className="modal modal-large">
              <div className="modal-header">
                <div>
                  <span className="eyebrow">CONFIGURAÇÃO DE RATEIO</span>
                  <h3>Unidades & Frações Ideais — {condominioUnidades.nome}</h3>
                </div>
                <button className="modal-close" onClick={() => setCondominioUnidades(null)}>×</button>
              </div>
              <div className="modal-body">
                <form onSubmit={salvarNovaUnidade} style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0', display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div style={{ flex: 2, minWidth: '180px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>Identificação da Unidade *</label>
                    <input type="text" placeholder="Ex: Ap 101, Apto 202, Cobertura 01" value={novaUnidade.identificacao} onChange={e => setNovaUnidade(p => ({ ...p, identificacao: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: '140px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>Fração Ideal (%) *</label>
                    <input type="text" placeholder="Ex: 2,5 ou 5,0" value={novaUnidade.fracao_ideal} onChange={e => setNovaUnidade(p => ({ ...p, fracao_ideal: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }} />
                  </div>
                  <button type="submit" className="button-primary" style={{ padding: '10px 20px', height: '42px' }}>+ Adicionar Unidade</button>
                </form>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '20px 0 10px 0' }}>
                  <h4 style={{ margin: 0, fontSize: '14px', textTransform: 'uppercase', color: '#334155' }}>Unidades Cadastradas ({listaUnidades.length})</h4>
                  <span style={{ fontSize: '13px', fontWeight: '700', color: Math.round(somaFracaoTotal) === 100 ? '#059669' : '#d97706' }}>
                    Soma das Frações: {formatarNumero(somaFracaoTotal)}% {Math.round(somaFracaoTotal) === 100 ? '✓ (100% Completo)' : '(Diferente de 100%)'}
                  </span>
                </div>

                <div style={{ maxHeight: '280px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                  {carregandoUnidades ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>Carregando unidades...</div>
                  ) : listaUnidades.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>Nenhuma unidade cadastrada para este condomínio. Cadastre acima!</div>
                  ) : (
                    <div className="table" style={{ margin: 0 }}>
                      <div className="table-header" style={{ gridTemplateColumns: '2fr 1fr 100px' }}>
                        <span>Identificação</span>
                        <span>Fração Ideal (%)</span>
                        <span style={{ textAlign: 'center' }}>Ação</span>
                      </div>
                      {listaUnidades.map(u => (
                        <div className="table-row" key={u.id} style={{ gridTemplateColumns: '2fr 1fr 100px' }}>
                          <strong>{u.identificacao}</strong>
                          <span style={{ fontWeight: '600', color: '#1d4ed8' }}>{formatarNumero(u.fracao_ideal)}%</span>
                          <div style={{ textAlign: 'center' }}>
                            <button className="text-button" style={{ color: 'var(--danger)', fontSize: '12px' }} onClick={() => excluirUnidade(u.id)}>Excluir</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={() => setCondominioUnidades(null)}>Fechar</button>
              </div>
            </div>
          </div>
        )}

        {solicitacaoSelecionada && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) fecharSolicitacao() }}>
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
                      {solicitacaoSelecionada.motivo_ajuste && (
                        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '20px' }}>📌</span>
                          <div>
                            <strong style={{ display: 'block', fontSize: '14px', color: '#991b1b', marginBottom: '4px' }}>Motivo do Ajuste / Reprovação</strong>
                            <span style={{ fontSize: '13px', color: '#b91c1c' }}>{solicitacaoSelecionada.motivo_ajuste}</span>
                          </div>
                        </div>
                      )}
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
                {!ehControladoria && ['Aprovação pendente', 'Ajuste solicitado'].includes(textoStatus(solicitacaoSelecionada.status)) && (
                  <>
                    <button className="button-primary" onClick={() => editarSolicitacao(solicitacaoSelecionada)}>Corrigir Pedido</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Pedido</button>
                  </>
                )}
                {ehControladoria && ['Aprovação pendente', 'Ajuste solicitado'].includes(textoStatus(solicitacaoSelecionada.status)) && (
                  <>
                    <button className="button-primary" onClick={() => aprovarSolicitacao(solicitacaoSelecionada)}>Aprovar Solicitação</button>
                    <button className="button-secondary" onClick={() => solicitarAjuste(solicitacaoSelecionada)}>Solicitar Ajuste</button>
                    <button className="button-danger" onClick={() => reprovarSolicitacao(solicitacaoSelecionada)}>Reprovar</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir</button>
                  </>
                )}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Aprovada' && (
                  <>
                    <button className="button-primary" onClick={() => iniciarExecucao(solicitacaoSelecionada)}>▶ Executar Solicitação</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button>
                  </>
                )}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Em execução' && (
                  <>
                    <button className="button-primary" style={{ backgroundColor: '#10b981', borderColor: '#10b981' }} onClick={() => finalizarSolicitacao(solicitacaoSelecionada)}>✓ Finalizar Solicitação</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button>
                  </>
                )}
                {ehControladoria && ['Finalizada', 'Reprovada'].includes(textoStatus(solicitacaoSelecionada.status)) && (
                  <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: '600', color: textoStatus(solicitacaoSelecionada.status) === 'Finalizada' ? '#059669' : '#dc2626' }}>
                      {textoStatus(solicitacaoSelecionada.status) === 'Finalizada' ? '✓ Solicitação finalizada' : '✕ Solicitação reprovada'}
                    </span>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Solicitação</button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {mostrarFormulario && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) fecharFormulario() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{solicitacaoEditando ? 'EDIÇÃO' : 'NOVA SOLICITAÇÃO'}</span><h3>{solicitacaoEditando ? 'Editar solicitação' : 'Criar Solicitação'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormulario}>×</button>
              </div>
              <div className="modal-body">
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
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormulario}>Cancelar</button>
                <button type="submit" className="button-primary" onClick={salvarSolicitacao} disabled={salvando}>{salvando ? 'Enviando...' : 'Enviar Solicitação'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarFormularioCondominio && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioCondominio() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{condominioEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{condominioEditando ? 'Editar Condomínio' : 'Cadastrar Condomínio'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioCondominio}>×</button>
              </div>
              <div className="modal-body">
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
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormularioCondominio} disabled={salvando}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarCondominio} disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarFormularioCategoria && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioCategoria() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{categoriaEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{categoriaEditando ? 'Editar Categoria' : 'Cadastrar Categoria'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioCategoria}>×</button>
              </div>
              <div className="modal-body">
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
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormularioCategoria} disabled={salvando}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarCategoria} disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarFormularioFornecedor && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioFornecedor() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{fornecedorEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{fornecedorEditando ? 'Editar Fornecedor' : 'Cadastrar Fornecedor'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioFornecedor}>×</button>
              </div>
              <div className="modal-body">
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
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormularioFornecedor} disabled={salvando}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarFornecedor} disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  )
}

export default App