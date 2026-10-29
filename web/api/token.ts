// Vercel function: POST /api/token (logic in server/token.ts).

import { jsonBody, respond } from '../server/http.js'
import { tokenDeps } from '../server/live.js'
import { token } from '../server/token.js'

export async function POST(request: Request): Promise<Response> {
  return respond(await token(request.headers.get('authorization'), await jsonBody(request), tokenDeps()))
}
