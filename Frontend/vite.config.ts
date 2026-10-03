import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

/**
 * Configuration Vite.
 *
 * - Alias `@` → `src` (imports explicites : `@/components/ui/button`).
 * - Proxy `/api` → backend FastAPI en dev : les appels passent en same-origin,
 *   pas de CORS à déclarer côté backend. La cible vient de `.env.development`
 *   (`VITE_PROXY_API`), pour cohabiter avec un autre service sur 8000.
 *   En production, servir le SPA derrière le domaine de l'API, ou définir
 *   `VITE_API_URL`.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': new URL('./src', import.meta.url).pathname,
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_API ?? 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
