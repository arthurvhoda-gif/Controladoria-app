// V7.6: leitor local do relatório de divergências, sem APIs ou armazenamento.
import { csvLinhas } from './custosConsolidacao.js'

const COLUNAS = ['tipo', 'condominio', 'id_registro', 'detalhe']

export function lerDivergenciasCsv(texto, registrosResumo) {
  if (!Array.isArray(registrosResumo) || !registrosResumo.length) {
    throw new Error('Primeiro selecione o resumo dos condomínios.')
  }
  const linhas = csvLinhas(texto)
  if (!linhas.length || linhas.length > 20001) {
    throw new Error('O relatório de divergências está vazio ou possui linhas demais.')
  }
  const nomes = linhas[0].map(x => x.trim().toLowerCase())
  if (nomes.length !== COLUNAS.length || new Set(nomes).size !== COLUNAS.length ||
      COLUNAS.some(k => !nomes.includes(k))) {
    throw new Error('Selecione divergencias.csv, gerado pela mesma auditoria.')
  }
  const indice = Object.fromEntries(COLUNAS.map(k => [k, nomes.indexOf(k)]))
  const resumo = new Map(registrosResumo.map(x => [x.nome.toLocaleLowerCase('pt-BR'), x]))
  const divergencias = linhas.slice(1).map((linha, pos) => {
    if (linha.length !== COLUNAS.length) {
      throw new Error('Colunas inválidas na linha ' + (pos + 2) + '.')
    }
    const valor = chave => linha[indice[chave]].trim()
    const tipo = valor('tipo')
    const condominio = valor('condominio')
    const id = valor('id_registro')
    const mensagem = valor('detalhe')
    if (!/^[A-Z][A-Z0-9_]{2,69}$/.test(tipo) ||
        !condominio || condominio.length > 180 || id.length > 256 ||
        !mensagem || mensagem.length > 4000) {
      throw new Error('Informações inválidas na linha ' + (pos + 2) + '.')
    }
    return { tipo, condominio, id, mensagem }
  })
  const contagem = new Map()
  for (const item of divergencias) {
    const nome = item.condominio.toLocaleLowerCase('pt-BR')
    contagem.set(nome, (contagem.get(nome) || 0) + 1)
  }
  for (const registro of registrosResumo) {
    const encontrado = contagem.get(registro.nome.toLocaleLowerCase('pt-BR')) || 0
    if (!registro.indisponivel && encontrado !== registro.divergencias) {
      throw new Error('Os relatórios não coincidem para ' + registro.nome +
        ': resumo=' + registro.divergencias + ', detalhes=' + encontrado +
        '. Gere uma nova auditoria antes de prosseguir.')
    }
  }
  // Os alertas globais sem condomínio identificado também são mantidos;
  // não fingir que os registros são todos de um condomínio conhecido.
  const semCorrespondencia = divergencias.filter(item =>
    !resumo.has(item.condominio.toLocaleLowerCase('pt-BR')))
  return { divergencias, semCorrespondencia: semCorrespondencia.length }
}

export function resumoPorTipo(registros) {
  const mapa = new Map()
  for (const { tipo } of registros) mapa.set(tipo, (mapa.get(tipo) || 0) + 1)
  return [...mapa].map(([tipo, quantidade]) => ({ tipo, quantidade }))
    .sort((a, b) => b.quantidade - a.quantidade || a.tipo.localeCompare(b.tipo))
}

export function tituloTipo(tipo) {
  const tipos = {
    NAO_ENCONTRADO_NA_BASE: 'Não encontrado na base geral',
    SOMENTE_NA_BASE: 'Existe apenas na base geral',
    DADOS_DIFERENTES: 'Informações diferentes',
    SEM_ID: 'Lançamento sem identificador',
    ID_DUPLICADO_BASE: 'Identificador repetido na base',
    ID_DUPLICADO_ORIGEM: 'Identificador repetido na origem',
    VALOR_INVALIDO: 'Valor inválido',
    DATA_INVALIDA: 'Data inválida',
    ARQUIVO_AUSENTE: 'Planilha de condomínio ausente',
    ERRO_LEITURA: 'Erro na leitura da planilha',
    PRAZO_AUSENTE_NA_BASE: 'Manutenção ausente na base',
    PRAZO_DIFERENTE: 'Prazo de manutenção divergente',
    CONDOMINIO_DESCONHECIDO: 'Condomínio desconhecido'
  }
  return tipos[tipo] || tipo.replaceAll('_', ' ').toLocaleLowerCase('pt-BR')
}
