import test from 'node:test'
import assert from 'node:assert/strict'
import { lerResumo, resumoGeral, centavos, csvLinhas } from './custosConsolidacao.js'
const cab = 'condominio;arquivo;despesas;classificadas;nao_classificadas;total_planilha;registros_na_base;total_base;manutencoes;divergencias'
const alfa = 'Alfa;ALFA.xlsm;11;10;1;R$ 1.250,50;7;R$ 950,40;1;3'
const beta = 'Beta;BETA.xlsm;7;7;0;R$ 410,00;7;R$ 410,00;0;0'
const ausente = 'Gama;GAMA.xlsm;-;-;-;-;-;-;-;arquivo ausente'
test('contabiliza CSV de auditoria ficticio sem rede', () => {
  const dados = lerResumo('\uFEFF' + cab + '\r\n' + alfa + '\r\n' + beta + '\r\n')
  assert.equal(dados.length, 2)
  assert.equal(dados[0].totalOrigem, 125050)
  assert.equal(dados[0].totalBase, 95040)
  assert.deepEqual(resumoGeral(dados), {condominios:2,indisponiveis:0,classificados:17,base:14,origemTotal:166050,baseTotal:136040,divergencias:3,comDivergencias:1})
})
test('nao transforma planilhas ausentes em zeros', () => {
  const dados = lerResumo([cab, alfa, ausente].join('\n'))
  assert.equal(resumoGeral(dados).indisponiveis, 1)
  assert.equal(resumoGeral(dados).origemTotal, 125050)
  assert.equal(dados[1].totalOrigem, null)
})
test('suporta aspas, ponto e virgula e quebras de linha', () => {
  const s = '"Alfa; ""Torre""\nB";ALFA.xlsm;11;10;1;R$ 1.250,50;7;R$ 950,40;1;3'
  assert.equal(lerResumo([cab,s].join('\n'))[0].nome, 'Alfa; "Torre"\nB')
})
test('rejeita arquivos incompatíveis e nomes repetidos', () => {
  assert.throws(() => lerResumo('nome;valor\nA;10'), /resumo_por_condominio/)
  assert.throws(() => lerResumo([cab,alfa,alfa].join('\n')), /duplicado/)
  assert.throws(() => lerResumo([cab,'Alfa;2'].join('\n')), /inconsistentes/)
  assert.throws(() => csvLinhas('"x'), /não fechadas/)
  assert.throws(() => centavos('1234,56'), /monetário inválido/)
})
