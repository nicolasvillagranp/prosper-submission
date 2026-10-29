// Vite config. Locally it reads the repo's ../.env (the same file Docker uses); on Vercel the same
// names come from the project's environment variables. Only the two public Supabase values reach
// the browser (plus two non-secret settings); everything else stays in the /api functions.
//
// In development, /api/<name> is served by api/<name>.ts, so `npm run dev` behaves like Vercel.

import type { IncomingMessage } from 'node:http'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type Plugin, type ViteDevServer } from 'vite'

function apiInDev(): Plugin {
  return {
    name: 'api-in-dev',
    configureServer(server: ViteDevServer) {
      server.middlewares.use(async (req, res, next) => {
        const name = req.url?.match(/^\/api\/([a-z-]+)/)?.[1]
        if (!name) return next()
        try {
          const mod = await server.ssrLoadModule(`/api/${name}.ts`)
          const handler = mod[req.method ?? 'GET']
          if (!handler) {
            res.statusCode = 405
            return res.end()
          }
          const response: Response = await handler(await toRequest(req))
          res.statusCode = response.status
          response.headers.forEach((value, key) => res.setHeader(key, value))
          res.end(Buffer.from(await response.arrayBuffer()))
        } catch (e) {
          server.config.logger.error(`/api/${name}: ${(e as Error).stack ?? e}`)
          res.statusCode = 500
          res.setHeader('content-type', 'application/json')
          res.end(JSON.stringify({ ok: false, error: 'Server error' }))
        }
      })
    },
  }
}

async function toRequest(req: IncomingMessage): Promise<Request> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  const headers = new Headers()
  for (const [key, value] of Object.entries(req.headers)) {
    if (typeof value === 'string') headers.set(key, value)
  }
  const body = ['GET', 'HEAD'].includes(req.method ?? 'GET') ? undefined : Buffer.concat(chunks)
  return new Request(`http://localhost${req.url}`, { method: req.method, headers, body })
}

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, '..', ''), ...process.env }
  // The /api functions read process.env, as on Vercel.
  Object.assign(process.env, loadEnv(mode, '..', ''))
  return {
    plugins: [react(), apiInDev()],
    // The live-interview chunk is the LiveKit client (~580 KB), loaded only when an interview starts.
    build: { chunkSizeWarningLimit: 700 },
    define: {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(env.SUPABASE_URL ?? ''),
      'import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY': JSON.stringify(env.SUPABASE_PUBLISHABLE_KEY ?? ''),
      // Not secrets: who sees the (mocked) dashboard link, and the interview length the agent enforces.
      'import.meta.env.VITE_ADMIN_EMAILS': JSON.stringify(env.ADMIN_EMAILS ?? ''),
      'import.meta.env.VITE_MAX_SESSION_MIN': JSON.stringify(env.MAX_SESSION_MIN ?? '20'),
    },
    test: { include: ['server/**/*.test.ts', 'src/**/*.test.{ts,tsx}'] },
  }
})
