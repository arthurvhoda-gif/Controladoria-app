
import { csvLinhas } from './custosConsolidacao'

// V7.7 — Leitura local dos gastos mensais.
// Nenhum dado é enviado ao servidor.
export function lerGastosMensaisCSV(texto) {
  const linhas = csvLinhas(texto)

  if (linhas.length < 2 || linhas.length > 5001) {
    throw new Error('Arquivo mensal vazio ou grande demais.')
  }

  const cabecalho = linhas[0].map(c => c.trim().toUpperCase())
  const campos = [
    'CONDOMINIO',
    'COMPETENCIA',
    'LANCAMENTOS',
    'VALOR_CENTAVOS'
  ]

  if (campos.some(c => !cabecalho.includes(c))) {
    throw new Error('CSV mensal com colunas incorretas.')
  }

  const indice = campo => cabecalho.indexOf(campo)
  const vistos = new Set()

  return linhas.slice(1).map((linha, posicao) => {
    if (linha.length !== cabecalho.length) {
      throw new Error(`Colunas inválidas na linha ${posicao + 2}.`)
    }

    const valor = campo => linha[indice(campo)].trim()
    const condominio = valor('CONDOMINIO')
    const data = valor('COMPETENCIA')
    const quantidade = Number(valor('LANCAMENTOS'))
    const centavos = Number(valor('VALOR_CENTAVOS'))

    const match = /^01\/(0[1-9]|1[0-2])\/(20\d{2})$/.exec(data)

    if (!condominio || condominio.length > 180 || !match) {
      throw new Error(`Condomínio ou mês inválido na linha ${posicao + 2}.`)
    }

    if (!Number.isSafeInteger(quantidade) || quantidade <= 0 ||
        !Number.isSafeInteger(centavos)) {
      throw new Error(`Valores inválidos na linha ${posicao + 2}.`)
    }

    const competencia = `${match[2]}-${match[1]}`
    const chave = `${condominio.toLowerCase()}|${competencia}`

    if (vistos.has(chave)) {
      throw new Error(`Mês duplicado na linha ${posicao + 2}.`)
    }

    vistos.add(chave)

    return {
      condominio,
      competencia,
      lancamentos: quantidade,
      valorCentavos: centavos
    }
  })
}
