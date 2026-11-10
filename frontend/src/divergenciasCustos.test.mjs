import test from 'node:test'
import assert from 'node:assert/strict'
import { lerDivergenciasCsv, resumoPorTipo, tituloTipo } from './divergenciasCustos.js'

const resumo = [
  { nome:'Max Living', divergencias:2, indisponivel:false },
  { nome:'Sunny Downtown', divergencias:1, indisponivel:false },
  { nome:'Poty Lazzarotto', divergencias:0, indisponivel:false },
]
const cab = 'tipo;condominio;id_registro;detalhe'
const max = 'NAO_ENCONTRADO_NA_BASE;Max Living;id-1;Despesa classificada ainda não está na base geral'
const max2 = 'NAO_ENCONTRADO_NA_BASE;Max Living;id-2;Despesa classificada ainda não está na base geral'
const sunny = 'DADOS_DIFERENTES;Sunny Downtown;id-3;"Descrição: origem=\"\"reparo\"\"; base=\"\"reparos\"\""'

test('lê relatórios locais compatíveis com resumo por condomínio', () => {
  const recebido = lerDivergenciasCsv(['\uFEFF' + cab, max, max2, sunny].join('\r\n'), resumo)
  assert.equal(recebido.divergencias.length, 3)
  assert.equal(recebido.semCorrespondencia, 0)
  assert.deepEqual(resumoPorTipo(recebido.divergencias), [
    { tipo:'NAO_ENCONTRADO_NA_BASE', quantidade:2 },
    { tipo:'DADOS_DIFERENTES', quantidade:1 },
  ])
  assert.equal(tituloTipo('NAO_ENCONTRADO_NA_BASE'), 'Não encontrado na base geral')
})

test('recusa relatório desatualizado e mantém dados de resumo separados', () => {
  assert.throws(() => lerDivergenciasCsv([cab, max].join('\n'), resumo), /não coincidem/)
  assert.throws(() => lerDivergenciasCsv([cab, max, max2, sunny].join('\n'), []), /Primeiro selecione/)
  assert.throws(() => lerDivergenciasCsv('nome;valor\nA;9', resumo), /Selecione divergencias.csv/)
  assert.throws(() => lerDivergenciasCsv([cab, max, 'XXX;Max Living;id-4'].join('\n'), resumo), /Colunas inválidas/)
})

test('reconhece ocorrência sem condomínio e não perde alertas globais', () => {
  const linhas = [cab, max, max2, sunny, 'ID_DUPLICADO_BASE;BASE_GERAL;id4;ID repetido'].join('\n')
  const resultado = lerDivergenciasCsv(linhas, resumo)
  assert.equal(resultado.semCorrespondencia, 1)
  assert.equal(resultado.divergencias.length, 4)
})

test('registra texto entre aspas em campo com ponto e vírgula', () => {
  const c = [cab, max, max2, sunny].join('\n')
  const resultado = lerDivergenciasCsv(c, resumo)
  assert.equal(resultado.divergencias[2].mensagem.includes(';'), true)
})
