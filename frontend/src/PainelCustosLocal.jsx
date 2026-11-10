import { useMemo, useState } from 'react'
import { lerResumo, resumoGeral, moeda } from './custosConsolidacao'
import { lerDivergenciasCsv, resumoPorTipo, tituloTipo } from './divergenciasCustos'
import './PainelCustosLocal.css'

export default function PainelCustosLocal() {
  const [linhas, setLinhas] = useState(null)
  const [arquivo, setArquivo] = useState('')
  const [erro, setErro] = useState('')
  const [filtro, setFiltro] = useState('todos')
  const [busca, setBusca] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [detalhes, setDetalhes] = useState(null)
  const [nomeDetalhes, setNomeDetalhes] = useState('')
  const [tipoSelecionado, setTipoSelecionado] = useState('todos')
  const [mostrarIdentificadores, setMostrarIdentificadores] = useState(false)
  const [carregandoDetalhes, setCarregandoDetalhes] = useState(false)
  const resumo = useMemo(() => linhas ? resumoGeral(linhas) : null, [linhas])
  const tipos = useMemo(() => detalhes ? resumoPorTipo(detalhes.divergencias) : [], [detalhes])
  const detalhesVisiveis = (detalhes?.divergencias || []).filter(item =>
    (tipoSelecionado === 'todos' || item.tipo === tipoSelecionado) &&
    (nomeDetalhes === 'todos' || item.condominio === nomeDetalhes))
  const visiveis = (linhas || []).filter(r =>
    r.nome.toLocaleLowerCase('pt-BR').includes(busca.toLocaleLowerCase('pt-BR')) &&
    (filtro === 'todos' || (filtro === 'pendente' && r.divergencias > 0) ||
      (filtro === 'regular' && r.divergencias === 0) ||
      (filtro === 'incompleto' && r.indisponivel)))
  async function carregar(evento) {
    const file = evento.target.files?.[0]
    evento.target.value = ''
    if (!file) return
    setCarregando(true)
    setErro('')
    try {
      if (!/\.csv$/i.test(file.name) || file.size > 2_000_000) throw new Error('Escolha um CSV de até 2 MB.')
      const texto = await file.text()
      setLinhas(lerResumo(texto))
      setArquivo(file.name)
      setDetalhes(null)
      setNomeDetalhes('')
      setTipoSelecionado('todos')
      setMostrarIdentificadores(false)
      setFiltro('todos')
      setBusca('')
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro ao ler o CSV.')
    } finally {
      setCarregando(false)
    }
  }
  async function carregarDetalhes(evento) {
    const file = evento.target.files?.[0]
    evento.target.value = ''
    if (!file || !linhas) return
    setCarregandoDetalhes(true)
    setErro('')
    try {
      if (file.name !== 'divergencias.csv' || file.size > 2_000_000) {
        throw new Error('Selecione divergencias.csv, com até 2 MB.')
      }
      const texto = await file.text()
      const validado = lerDivergenciasCsv(texto, linhas)
      setDetalhes(validado)
      setNomeDetalhes('todos')
      setTipoSelecionado('todos')
      setMostrarIdentificadores(false)
    } catch (e) {
      setDetalhes(null)
      setErro(e instanceof Error ? e.message : 'Não foi possível conferir o relatório detalhado.')
    } finally {
      setCarregandoDetalhes(false)
    }
  }
  function limpar() {
    setLinhas(null); setArquivo(''); setErro(''); setFiltro('todos'); setBusca('')
    setDetalhes(null); setNomeDetalhes(''); setTipoSelecionado('todos'); setMostrarIdentificadores(false)
  }
  return <section className="hc-painel" aria-label="Conciliação local de custos">
    <div className="hc-hero">
      <div>
        <small>INTELIGÊNCIA DE CUSTOS · V7.6</small>
        <h2>Conciliação dos condomínios</h2>
        <p>Compare a base geral com as despesas classificadas nas planilhas individuais.</p>
        <p className="hc-privacidade">Privacidade: o relatório é lido somente neste navegador. Não é enviado ao servidor, não fica salvo e não altera as planilhas.</p>
      </div>
      <div className="hc-importar">
        <label htmlFor="hc-arquivo">Selecionar resumo CSV</label>
        <input id="hc-arquivo" type="file" accept=".csv,text/csv" onChange={carregar} disabled={carregando} />
        <small>Use resumo_por_condominio.csv da auditoria V7.6</small>
        {linhas && <button type="button" onClick={limpar}>Limpar dados desta tela</button>}
      </div>
    </div>
    {erro && <p role="alert" className="hc-erro">{erro}</p>}
    {!resumo ? <div className="hc-vazio">
      <h3>Carregue seu relatório local</h3>
      <p>Na pasta Documentos → Haize_Auditoria_Custos_V76, selecione <strong>resumo_por_condominio.csv</strong>.</p>
      <p>Nenhum dado real foi inserido nesta página. Os resultados desaparecerão ao atualizar a tela.</p>
    </div> : <>
      <p className="hc-status" role="status">Relatório local: <strong>{arquivo}</strong>. Não houve importação para o Neon.</p>
      <div className="hc-kpis">
        <article><span>Condomínios</span><strong>{resumo.condominios}</strong></article>
        <article><span>Classificados</span><strong>{resumo.classificados.toLocaleString('pt-BR')}</strong></article>
        <article><span>Registros na base</span><strong>{resumo.base.toLocaleString('pt-BR')}</strong></article>
        <article><span>Divergências</span><strong>{resumo.divergencias}</strong></article>
      </div>
      <div className="hc-totais">
        <div><span>Origem (planilhas)</span><strong>{moeda(resumo.origemTotal)}</strong></div>
        <div><span>Base geral</span><strong>{moeda(resumo.baseTotal)}</strong></div>
        <div><span>Diferença dos totais</span><strong>{moeda(resumo.origemTotal - resumo.baseTotal)}</strong></div>
      </div>
      {resumo.indisponiveis > 0 && <p className="hc-erro">{resumo.indisponiveis} condomínio(s) com dados indisponíveis; os totais não os incluem.</p>}
      <div className="hc-tabela-bloco">
        <div className="hc-filtros">
          <div><h3>Condomínios</h3><p>{resumo.comDivergencias} com alertas</p></div>
          <label>Buscar <input type="search" placeholder="Nome do condomínio" value={busca} onChange={e => setBusca(e.target.value)}/></label>
          <label>Situação <select value={filtro} onChange={e => setFiltro(e.target.value)}>
            <option value="todos">Todos</option>
            <option value="pendente">Com divergências</option>
            <option value="regular">Sem divergências</option>
            <option value="incompleto">Dados indisponíveis</option>
          </select></label>
        </div>
        <div className="hc-scroll">
          <table><thead><tr><th>Condomínio</th><th>Classificados</th><th>Na base</th><th>Total planilhas</th><th>Total base</th><th>Alertas</th></tr></thead>
            <tbody>{visiveis.map(r => <tr key={r.nome}>
              <th scope="row">{r.nome}</th><td>{r.classificados ?? '—'}</td><td>{r.base ?? '—'}</td><td>{moeda(r.totalOrigem)}</td><td>{moeda(r.totalBase)}</td>
              <td><span className={'hc-selo ' + (r.indisponivel ? 'hc-neutro' : r.divergencias ? 'hc-alerta' : 'hc-ok')}>{r.indisponivel ? 'Sem dados' : r.divergencias ? r.divergencias + ' alerta(s)' : 'Conferido'}</span></td>
            </tr>)}</tbody>
          </table>
          {visiveis.length === 0 && <p className="hc-sem">Nenhum condomínio corresponde aos filtros.</p>}
        </div>
      </div>
      <section className="hc-detalhes" aria-label="Revisão das divergências">
        <div className="hc-detalhes-cabecalho">
          <div>
            <h3>Conferência das divergências</h3>
            <p>Para visualizar os tipos de alerta e localizar as pendências, escolha o arquivo detalhado da mesma auditoria.</p>
            <p>O arquivo é lido somente nesta página, sem upload. Não corrige planilhas e não gera lançamentos.</p>
          </div>
          <label className="hc-detalhes-seletor">
            Selecionar divergencias.csv
            <input type="file" accept=".csv,text/csv" onChange={carregarDetalhes} disabled={carregandoDetalhes} />
          </label>
        </div>
        {detalhes && <>
          <p className="hc-status" role="status">{detalhes.divergencias.length} ocorrências conferidas com o resumo. {detalhes.semCorrespondencia > 0 ? detalhes.semCorrespondencia + ' fora dos condomínios do resumo.' : 'Nenhuma ocorrência fora dos condomínios do resumo.'}</p>
          <div className="hc-tipologia">
            {tipos.map(item => <div key={item.tipo}>
              <strong>{item.quantidade}</strong><span>{tituloTipo(item.tipo)}</span>
            </div>)}
          </div>
          <div className="hc-filtros hc-filtros-detalhes">
            <div><h3>Ocorrências</h3><p>Confirme as diferenças na planilha de origem antes de qualquer consolidação.</p></div>
            <label>Condomínio <select value={nomeDetalhes} onChange={e => setNomeDetalhes(e.target.value)}>
              <option value="todos">Todos</option>
              {Array.from(new Set(detalhes.divergencias.map(item => item.condominio))).sort((a,b)=>a.localeCompare(b,'pt-BR')).map(nome => <option key={nome} value={nome}>{nome}</option>)}
            </select></label>
            <label>Tipo de ocorrência <select value={tipoSelecionado} onChange={e => setTipoSelecionado(e.target.value)}>
              <option value="todos">Todos os tipos</option>
              {tipos.map(item => <option key={item.tipo} value={item.tipo}>{tituloTipo(item.tipo)}</option>)}
            </select></label>
          </div>
          <label className="hc-opcao-ids">
            <input type="checkbox" checked={mostrarIdentificadores} onChange={e => setMostrarIdentificadores(e.target.checked)} />
            Exibir identificadores e observações dos lançamentos (informações financeiras locais)
          </label>
          <div className="hc-scroll"><table><thead><tr>
            <th>Condomínio</th><th>Tipo</th>{mostrarIdentificadores && <><th>ID de origem</th><th>Observação</th></>}
          </tr></thead><tbody>{detalhesVisiveis.map((item,i) => <tr key={item.tipo + '-' + item.condominio + '-' + item.id + '-' + i}>
            <th scope="row">{item.condominio}</th><td>{tituloTipo(item.tipo)}</td>
            {mostrarIdentificadores && <><td>{item.id || '—'}</td><td>{item.mensagem}</td></>}
          </tr>)}</tbody></table>
          {!detalhesVisiveis.length && <p className="hc-sem">Nenhuma ocorrência nos filtros selecionados.</p>}
          </div>
        </>}
      </section>
      <p className="hc-nota">A diferença entre os totais não representa economia e não prova ausência de lançamentos duplicados. Não corrija ou importe os dados sem conferência.</p>
    </>}
  </section>
}
