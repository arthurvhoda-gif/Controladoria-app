import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Controladoria App',
        short_name: 'Controladoria',
        description: 'Sistema de Gestão da Controladoria',
        theme_color: '#000000',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [
          {
            src: 'https://cdn-icons-png.flaticon.com/512/3256/3256013.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'https://cdn-icons-png.flaticon.com/512/3256/3256013.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ]
})