import { describe, expect, it } from 'vitest'

import { signup, type SignupDeps } from './signup'

function deps(emails: string[], maxUsers = 3, allowedEmails: string[] = []): SignupDeps & { created: string[] } {
  const created: string[] = []
  return {
    inviteCode: 'secret-code',
    allowedEmails,
    adminEmails: ['boss@x.com'],
    maxUsers,
    created,
    listEmails: async () => emails,
    createUser: async (email) => {
      created.push(email)
    },
  }
}

describe('signup', () => {
  it('creates the account with the right code', async () => {
    const d = deps(['a@x.com'])
    const r = await signup({ email: '  New@X.com ', code: 'secret-code' }, d)
    expect(r).toEqual({ status: 200, body: { ok: true, existing: false } })
    expect(d.created).toEqual(['new@x.com'])
  })

  it('rejects a wrong code before revealing anything', async () => {
    const d = deps(['a@x.com'])
    expect((await signup({ email: 'a@x.com', code: 'nope' }, d)).status).toBe(403)
    expect(d.created).toEqual([])
  })

  it('lets an existing user through without creating anything', async () => {
    const d = deps(['a@x.com'])
    expect((await signup({ email: 'A@x.com', code: 'secret-code' }, d)).body).toEqual({ ok: true, existing: true })
    expect(d.created).toEqual([])
  })

  it('stops at the user cap', async () => {
    const d = deps(['a@x.com', 'b@x.com'], 2)
    const r = await signup({ email: 'c@x.com', code: 'secret-code' }, d)
    expect(r.status).toBe(403)
    expect(r.body.error).toMatch(/invitations are taken/)
  })

  it('needs a valid email', async () => {
    expect((await signup({ email: 'nope', code: 'secret-code' }, deps([]))).status).toBe(400)
  })

  it('asks for the code when none was given', async () => {
    const r = await signup({ email: 'new@x.com' }, deps([]))
    expect(r.status).toBe(403)
    expect(r.body.needs_code).toBe(true)
  })

  describe('with an invite list', () => {
    const list = ['guest@example.com']

    it('lets listed emails in without a code', async () => {
      const d = deps([], 3, list)
      expect((await signup({ email: 'Guest@Example.com' }, d)).status).toBe(200)
      expect(d.created).toEqual(['guest@example.com'])
    })

    it('keeps everyone else out, even with the right code', async () => {
      const d = deps([], 3, list)
      const r = await signup({ email: 'stranger@x.com', code: 'secret-code' }, d)
      expect(r.status).toBe(403)
      expect(r.body.error).toMatch(/invite list/)
      expect(d.created).toEqual([])
    })

    it('always lets admins in', async () => {
      expect((await signup({ email: 'boss@x.com' }, deps([], 3, list))).status).toBe(200)
    })

    it('still respects the user cap', async () => {
      expect((await signup({ email: 'guest@example.com' }, deps(['a@x.com'], 1, list))).status).toBe(403)
    })
  })
})
