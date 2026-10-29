// Vercel function: POST /api/signup (logic in server/signup.ts).

import { jsonBody, respond } from '../server/http.js'
import { signupDeps } from '../server/live.js'
import { signup } from '../server/signup.js'

export async function POST(request: Request): Promise<Response> {
  return respond(await signup(await jsonBody(request), signupDeps()))
}
