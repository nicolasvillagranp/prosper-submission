// Small helpers shared by the /api functions.

export interface Result {
  status: number
  body: Record<string, unknown>
}

export const ok = (body: Record<string, unknown> = {}): Result => ({ status: 200, body: { ok: true, ...body } })
export const fail = (status: number, error: string): Result => ({ status, body: { ok: false, error } })

export function respond(result: Result): Response {
  return Response.json(result.body, { status: result.status })
}

export async function jsonBody(request: Request): Promise<Record<string, unknown>> {
  try {
    const body = await request.json()
    return body && typeof body === 'object' ? (body as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

export function env(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`Missing ${name} in the environment (.env locally, Vercel settings in production)`)
  return value
}
