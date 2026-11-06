/**
 * Exportador XLSX V7.1: compatibilidade com o modelo de relatórios da Haize.
 *
 * Usa ExcelJS mantido no npm no lugar de xlsx / xlsx-js-style.
 * Não interpreta ou importa arquivos fornecidos por usuários.
 * Os textos recebidos são sempre células de TEXTO, nunca fórmulas.
 * Apenas fórmulas definidas pelo próprio código têm a propriedade `f`.
 */

function corArgb(cor) {
  const rgb = cor?.rgb
  if (typeof rgb !== 'string' || !/^(?:[0-9a-f]{6}|[0-9a-f]{8})$/i.test(rgb)) return undefined
  return { argb: rgb.length === 6 ? `FF${rgb.toUpperCase()}` : rgb.toUpperCase() }
}

function estiloExcel(style) {
  if (!style || typeof style !== 'object') return {}
  const saida = {}
  if (style.font) {
    const f = style.font
    saida.font = {
      ...(f.name ? { name: String(f.name) } : {}),
      ...(Number.isFinite(f.sz) ? { size: f.sz } : {}),
      ...(f.bold ? { bold: true } : {}),
      ...(f.italic ? { italic: true } : {}),
      ...(corArgb(f.color) ? { color: corArgb(f.color) } : {}),
    }
  }
  if (style.fill?.fgColor) {
    const cor = corArgb(style.fill.fgColor)
    if (cor) saida.fill = { type: 'pattern', pattern: 'solid', fgColor: cor }
  }
  if (style.alignment) {
    const a = style.alignment
    saida.alignment = {
      ...(a.horizontal ? { horizontal: a.horizontal } : {}),
      ...(a.vertical ? { vertical: a.vertical === 'center' ? 'middle' : a.vertical } : {}),
      ...(a.wrapText ? { wrapText: true } : {}),
    }
  }
  if (style.border) {
    saida.border = {}
    for (const lado of ['top', 'bottom', 'left', 'right']) {
      const b = style.border[lado]
      if (!b) continue
      saida.border[lado] = {
        ...(b.style ? { style: b.style } : {}),
        ...(corArgb(b.color) ? { color: corArgb(b.color) } : {}),
      }
    }
  }
  return saida
}

export function criarAdaptadorXlsx(ExcelJS) {
  if (typeof ExcelJS?.Workbook !== 'function') {
    throw new Error('Não foi possível inicializar o motor de relatórios Excel.')
  }
  return {
    utils: {
      book_new: () => new ExcelJS.Workbook(),
      aoa_to_sheet: linhas => ({ linhas, '!merges': [], '!cols': [] }),
      book_append_sheet: (wb, antigaAba, nome) => {
        const aba = wb.addWorksheet(nome)
        antigaAba.linhas.forEach((linha, r) => {
          if (!Array.isArray(linha)) return
          linha.forEach((entrada, c) => {
            if (entrada == null) return
            const celula = aba.getCell(r + 1, c + 1)
            const d = typeof entrada === 'object' && !Array.isArray(entrada) ? entrada : { v: entrada }
            // Valores de entradas (usuário, condomínio, fornecedor) SEMPRE são
            // textos literais. Somente f explícito do código gera fórmula.
            if (typeof d.f === 'string') {
              celula.value = { formula: d.f, result: d.v ?? null }
            } else if (d.v != null) {
              celula.value = d.t === 's' ? String(d.v) : d.v
            }
            const e = estiloExcel(d.s)
            if (e.font) celula.font = e.font
            if (e.fill) celula.fill = e.fill
            if (e.alignment) celula.alignment = e.alignment
            if (e.border) celula.border = e.border
            if (d.z) celula.numFmt = d.z
          })
        })
        antigaAba['!cols']?.forEach((coluna, i) => {
          if (Number.isFinite(coluna?.wch) && coluna.wch > 0) {
            aba.getColumn(i + 1).width = coluna.wch + 2
          }
        })
        antigaAba['!merges']?.forEach(({ s, e }) => {
          aba.mergeCells(s.r + 1, s.c + 1, e.r + 1, e.c + 1)
        })
        return aba
      },
    },
    writeFile: async (wb, nome) => {
      const bytes = await wb.xlsx.writeBuffer()
      const blob = new Blob([bytes], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = String(nome).replace(/[\\/\p{Cc}]/gu, '_').slice(0, 160)
      document.body.appendChild(link)
      try {
        link.click()
      } finally {
        link.remove()
        // Revogar após a ação permite que o navegador finalize o download.
        setTimeout(() => URL.revokeObjectURL(url), 30_000)
      }
    },
  }
}

export async function carregarAdaptadorXlsx() {
  // Carregamento sob demanda: a biblioteca não pesa na abertura do aplicativo.
  const modulo = await import('exceljs/dist/exceljs.min.js')
  return criarAdaptadorXlsx(modulo.default || modulo)
}
