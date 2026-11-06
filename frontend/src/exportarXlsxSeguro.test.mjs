import assert from 'node:assert/strict'
import test from 'node:test'
import { criarAdaptadorXlsx } from './exportarXlsxSeguro.js'

class FalsaAba {
  constructor(nome) { this.name = nome; this.celulas = new Map(); this.colunas = new Map(); this.mesclas = [] }
  getCell(linha, coluna) {
    const chave = `${linha}:${coluna}`
    if (!this.celulas.has(chave)) this.celulas.set(chave, {})
    return this.celulas.get(chave)
  }
  getColumn(n) {
    if (!this.colunas.has(n)) this.colunas.set(n, {})
    return this.colunas.get(n)
  }
  mergeCells(...args) { this.mesclas.push(args) }
}
class FalsoWorkbook {
  constructor() { this.worksheets = []; this.xlsx = { writeBuffer: async () => new Uint8Array([80, 75, 3, 4]) } }
  addWorksheet(nome) { const aba = new FalsaAba(nome); this.worksheets.push(aba); return aba }
}
const XLSX = criarAdaptadorXlsx({ Workbook: FalsoWorkbook })

test('preserva duas abas, mesclas, largura e cores sem expor valores', () => {
  const wb = XLSX.utils.book_new()
  const sh = XLSX.utils.aoa_to_sheet([
    [{ v: 'RESUMO', s: { font: { name: 'Calibri', sz: 14, bold: true, color: { rgb: 'FFFFFF' } }, fill: { fgColor: { rgb: '0F172A' } } } }],
    [{ v: 10.5, t: 'n', z: '"R$" #,##0.00', s: { alignment: { horizontal: 'right', vertical: 'center' } } }],
  ])
  sh['!cols'] = [{ wch: 28 }]
  sh['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 1 } }]
  XLSX.utils.book_append_sheet(wb, sh, 'Resumo por Condomínio')
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([[{ v: 'EXTRATO' }]]), 'Extrato de Solicitações')
  assert.deepEqual(wb.worksheets.map(x => x.name), ['Resumo por Condomínio', 'Extrato de Solicitações'])
  const resumo = wb.worksheets[0]
  assert.deepEqual(resumo.mesclas, [[1, 1, 1, 2]])
  assert.equal(resumo.getColumn(1).width, 30)
  assert.equal(resumo.getCell(1, 1).font.color.argb, 'FFFFFFFF')
  assert.equal(resumo.getCell(1, 1).fill.fgColor.argb, 'FF0F172A')
  assert.equal(resumo.getCell(2, 1).numFmt, '"R$" #,##0.00')
  assert.equal(resumo.getCell(2, 1).alignment.vertical, 'middle')
})

test('conserva formulas consolidadas como formulas reais e valor calculado', () => {
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
    [{ v: 10, t: 'n' }],
    [{ f: 'SUM(A1:A1)', v: 10, t: 'n' }],
  ]), 'Consolidação')
  assert.deepEqual(wb.worksheets[0].getCell(2, 1).value, { formula: 'SUM(A1:A1)', result: 10 })
})

test('texto controlado pelo usuário nunca vira formula, mesmo iniciando com =, +, @', () => {
  const wb = XLSX.utils.book_new()
  const valores = ['=1+1', '+SUM(1,2)', '@nome', '-999', 'normal']
  XLSX.utils.book_append_sheet(wb,
    XLSX.utils.aoa_to_sheet(valores.map(v => [{ v, t: 's' }])), 'Segurança')
  valores.forEach((v, i) => assert.equal(wb.worksheets[0].getCell(i + 1, 1).value, v))
})

test('formatação de status, bordas, negrito e tipografia preservados', () => {
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([[
    { v: 'Economia', t: 's', s: {
      font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '065F46' } },
      fill: { fgColor: { rgb: 'D1FAE5' } },
      border: { top: { style: 'thin', color: { rgb: 'CBD5E1' } } },
      alignment: { horizontal: 'center', vertical: 'center', wrapText: true },
    } },
  ]]), 'Cores')
  const c = wb.worksheets[0].getCell(1, 1)
  assert.equal(c.font.name, 'Calibri')
  assert.equal(c.font.size, 11)
  assert.equal(c.font.bold, true)
  assert.equal(c.fill.fgColor.argb, 'FFD1FAE5')
  assert.equal(c.border.top.style, 'thin')
  assert.equal(c.alignment.wrapText, true)
})
