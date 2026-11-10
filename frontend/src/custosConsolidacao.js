// V7.6: leitura local do resumo CSV da auditoria. Nao envia dados ao servidor.
export function csvLinhas(texto) {
  if (typeof texto !== 'string' || texto.length > 2_000_000) throw new Error('Arquivo inválido ou maior que 2 MB.')
  const t = texto.replace(/^\uFEFF/, '')
  const rows = []
  let row = [], value = '', quoted = false
  for (let i = 0; i < t.length; i++) {
    const c = t[i]
    if (c === '"') {
      if (quoted && t[i + 1] === '"') { value += '"'; i++ }
      else if (quoted) quoted = false
      else if (value === '') quoted = true
      else throw new Error('Aspas inválidas no CSV.')
    } else if (c === ';' && !quoted) { row.push(value); value = '' }
    else if ((c === '\r' || c === '\n') && !quoted) {
      if (c === '\r' && t[i + 1] === '\n') i++
      row.push(value)
      if (row.some(x => x.trim())) rows.push(row)
      row = []; value = ''
    } else value += c
  }
  if (quoted) throw new Error('Aspas não fechadas no CSV.')
  row.push(value)
  if (row.some(x => x.trim())) rows.push(row)
  return rows
}
function numero(v, coluna) {
  if (!/^\d+$/.test(v)) throw new Error('Número inválido em ' + coluna)
  const n = Number(v)
  if (!Number.isSafeInteger(n)) throw new Error('Número fora do limite em ' + coluna)
  return n
}
export function centavos(v) {
  const m = /^R\$\s*(-?)(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})$/.exec(v)
  if (!m) throw new Error('Valor monetário inválido.')
  const result = Number(m[2].replace(/\./g, '')) * 100 + Number(m[3])
  if (!Number.isSafeInteger(result)) throw new Error('Valor fora do limite.')
  return m[1] === '-' ? -result : result
}
export function lerResumo(texto) {
  const rows = csvLinhas(texto)
  if (rows.length < 2 || rows.length > 201) throw new Error('CSV sem registros ou com linhas demais.')
  const head = rows[0].map(s => s.trim().toLowerCase())
  const campos = ['condominio','arquivo','despesas','classificadas','nao_classificadas','total_planilha','registros_na_base','total_base','manutencoes','divergencias']
  if (new Set(head).size !== head.length || campos.some(c => !head.includes(c))) {
    throw new Error('Selecione o arquivo resumo_por_condominio.csv da auditoria V7.6.')
  }
  const idx = Object.fromEntries(campos.map(c => [c, head.indexOf(c)]))
  const seen = new Set()
  return rows.slice(1).map((row, j) => {
    if (row.length !== head.length) throw new Error('Colunas inconsistentes na linha ' + (j + 2))
    const get = col => row[idx[col]].trim()
    const nome = get('condominio')
    const normalized = nome.toLocaleLowerCase('pt-BR')
    if (!nome || nome.length > 180 || seen.has(normalized)) throw new Error('Condomínio ausente ou duplicado na linha ' + (j + 2))
    seen.add(normalized)
    const indisponivel = ['classificadas','total_planilha','registros_na_base','total_base','divergencias'].some(c => get(c) === '-' || get(c) === 'arquivo ausente')
    return {
      nome, indisponivel,
      classificados: indisponivel ? null : numero(get('classificadas'), 'classificadas'),
      base: indisponivel ? null : numero(get('registros_na_base'), 'registros_na_base'),
      totalOrigem: indisponivel ? null : centavos(get('total_planilha')),
      totalBase: indisponivel ? null : centavos(get('total_base')),
      divergencias: indisponivel ? null : numero(get('divergencias'), 'divergencias')
    }
  })
}
export function resumoGeral(rows) {
  const validos = rows.filter(r => !r.indisponivel)
  const soma = campo => validos.reduce((acc, row) => acc + row[campo], 0)
  return {
    condominios: rows.length, indisponiveis: rows.length - validos.length,
    classificados: soma('classificados'), base: soma('base'),
    origemTotal: soma('totalOrigem'), baseTotal: soma('totalBase'),
    divergencias: soma('divergencias'), comDivergencias: validos.filter(r => r.divergencias > 0).length
  }
}
export function moeda(v) {
  return v === null ? '—' : new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'}).format(v / 100)
}
