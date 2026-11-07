import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Exclusivamente na demonstracao local: nao requisitar fontes remotas.
// A versao normal mantem o CSS original e todas as fontes configuradas.
const semFontesExternasNaDemo = {
  name: 'haize-demo-v73-fontes-locais',
  enforce: 'pre',
  transform(codigo, id) {
    const caminho = id.replaceAll(String.fromCharCode(92), '/').split('?')[0]
    if (process.env.VITE_HAIZE_DEMO_V73 !== '1' ||
        !caminho.endsWith('/src/App.css')) return null
    return codigo.replace(
      /^@import\s+url\(['"]https:\/\/fonts\.googleapis\.com\/[^'"]+['"]\);\s*/m,
      ''
    )
  },
}

export default defineConfig({
  plugins: [
    semFontesExternasNaDemo,
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'script', // Força a injeção do motor
      manifest: {
        name: 'Controladoria App',
        short_name: 'Controladoria',
        description: 'Sistema de Gestão da Controladoria',
        theme_color: '#000000',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [
          {
            src: '/logo.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/logo.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ]
})