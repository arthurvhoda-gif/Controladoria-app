
import { useMemo, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line,
  BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip
} from 'recharts'
import { lerGastosMensaisCSV } from './intelligenceMensal'

const moeda = centavos =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(centavos / 100)

const estilo = {
  painel: { display: 'grid', gap: 20 },
  filtros: {
    display: 'flex', gap: 12,
    flexWrap: 'wrap', alignItems: 'center'
  },
  cards: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
    gap: 12
  },
  card: {
    background: '#fff', border: '1px solid #d9e4ef',
    borderRadius: 12, padding: 18
  },
  grafico: {
    background: '#fff', border: '1px solid #d9e4ef',
    borderRadius: 12, padding: 18
  }
}

export default function HaizeIntelligence() {
  const [dados, setDados] = useState([])
  const [arquivo, setArquivo] = useState('')
  const [erro, setErro] = useState('')
  const [condominio, setCondominio] = useState('todos')
  const [ano, setAno] = useState('todos')

  async function carregar(evento) {
    const file = evento.target.files?.[0]
    evento.target.value = ''
    if (!file) return

    setErro('')
    try {
      if (!/\.csv$/i.test(file.name) || file.size > 2000000) {
        throw new Error('Selecione um CSV de até 2 MB.')
      }

      const linhas = lerGastosMensaisCSV(await file.text())
      setDados(linhas)
      setArquivo(file.name)
      setCondominio('todos')
      setAno('todos')
    } catch (e) {
      setErro(e.message || 'Erro ao carregar arquivo.')
    }
  }

  const condominios = useMemo(() =>
    [...new Set(dados.map(d => d.condominio))].sort(),
    [dados]
  )

  const anos = useMemo(() =>
    [...new Set(dados.map(d => d.competencia.slice(0, 4)))].sort(),
    [dados]
  )

  const filtrados = useMemo(() => dados.filter(d =>
    (condominio === 'todos' || d.condominio === condominio) &&
    (ano === 'todos' || d.competencia.startsWith(ano))
  ), [dados, condominio, ano])

  const total = filtrados.reduce((s, d) => s + d.valorCentavos, 0)
  const lancamentos = filtrados.reduce((s, d) => s + d.lancamentos, 0)

  const mensal = useMemo(() => {
    const valores = new Map()

    for (const d of filtrados) {
      valores.set(
        d.competencia,
        (valores.get(d.competencia) || 0) + d.valorCentavos
      )
    }

    return [...valores].sort(([a], [b]) => a.localeCompare(b))
      .map(([mes, valor]) => ({
        mes,
        valor,
        label: mes.slice(5, 7) + '/' + mes.slice(0, 4)
      }))
  }, [filtrados])

  const porCondominio = useMemo(() => {
    const valores = new Map()

    for (const d of filtrados) {
      valores.set(
        d.condominio,
        (valores.get(d.condominio) || 0) + d.valorCentavos
      )
    }

    return [...valores].map(([nome, valor]) => ({
      nome,
      valor
    })).sort((a, b) => b.valor - a.valor)
  }, [filtrados])

  return (
    <section style={estilo.painel}>
      <header>
        <small>HAIZE INTELLIGENCE · V7.7</small>
        <h2>Visão Executiva de Custos</h2>
        <p>Análise histórica por condomínio e competência mensal.</p>
        <p>
          Dados processados localmente no navegador.
          Nenhum arquivo financeiro é enviado ao servidor.
        </p>
      </header>

      <div style={estilo.filtros}>
        <label>
          Arquivo mensal
          <input type="file" accept=".csv" onChange={carregar} />
        </label>

        <label>
          Condomínio
          <select value={condominio}
            onChange={e => setCondominio(e.target.value)}>
            <option value="todos">Todos</option>
            {condominios.map(c =>
              <option key={c} value={c}>{c}</option>
            )}
          </select>
        </label>

        <label>
          Ano
          <select value={ano}
            onChange={e => setAno(e.target.value)}>
            <option value="todos">Todo o histórico</option>
            {anos.map(a =>
              <option key={a} value={a}>{a}</option>
            )}
          </select>
        </label>
      </div>

      {erro && <p role="alert">{erro}</p>}

      {!dados.length ? (
        <div style={estilo.card}>
          Selecione o arquivo 02_GASTOS_MENSAIS_V77.csv
          para iniciar a análise.
        </div>
      ) : (
        <>
          <p>Arquivo local carregado: {arquivo}</p>

          <div style={estilo.cards}>
            {[
              ['Total de despesas', moeda(total)],
              ['Lançamentos', lancamentos.toLocaleString('pt-BR')],
              ['Condomínios', porCondominio.length],
              ['Meses com registros', mensal.length]
            ].map(([titulo, valor]) => (
              <article style={estilo.card} key={titulo}>
                <small>{titulo}</small>
                <h2>{valor}</h2>
              </article>
            ))}
          </div>

          <article style={estilo.grafico}>
            <h3>Evolução mensal das despesas</h3>
            <div style={{ width: '100%', height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={mensal}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis tickFormatter={v => `${Math.round(v / 100000)} mil`} />
                  <Tooltip formatter={v => moeda(v)} />
                  <Line dataKey="valor" name="Despesas"
                    stroke="#24517d" strokeWidth={3} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article style={estilo.grafico}>
            <h3>Despesas por condomínio</h3>
            <div style={{
              width: '100%',
              height: Math.max(300, porCondominio.length * 45)
            }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={porCondominio} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number"
                    tickFormatter={v => `${Math.round(v / 100000)} mil`} />
                  <YAxis type="category" dataKey="nome"
                    width={175} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={v => moeda(v)} />
                  <Bar dataKey="valor" name="Despesas"
                    fill="#24517d" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          <small>
            Meses sem registros não são tratados automaticamente
            como meses de despesa zero. Os valores representam
            despesas históricas, não economia obtida.
          </small>
        </>
      )}
    </section>
  )
}
