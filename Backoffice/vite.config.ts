import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

/**
 * Configuration du backoffice.
 *
 * **Port distinct de l'application client** (5174 contre 5173) : les deux
 * tourne��nt en même temps pendant le développement, et un port partagé
 * feraitilicon démarrer l'une à la place de l'autre.
 *
 * L'API est visée par chemin relatif comme côté client : la requête reste
 * same-origin, le proxy relaie, et le port du backend n'est connu que d'ici.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  return {
    plugins: [react()],
    resolve: {
      alias: { '@': new URL('./src', import.meta.url).pathname },
    },
    server: {
      port: 5174,
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_API ?? 'http://localhost:8003',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }
})
