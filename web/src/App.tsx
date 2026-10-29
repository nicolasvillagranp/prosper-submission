import type { Session } from '@supabase/supabase-js'
import { lazy, Suspense, useEffect, useState } from 'react'

import Header from './components/Header'
import { usePath } from './lib/router'
import { ADMIN_EMAILS, supabase } from './lib/supabase'
import type { Profile } from './lib/types'
import Admin from './screens/Admin'
import Episodes from './screens/Episodes'
import Onboarding from './screens/Onboarding'
import Settings from './screens/Settings'
import SignIn from './screens/SignIn'
import Today from './screens/Today'
import TopicPage from './screens/TopicPage'

// The live screen carries the LiveKit client (~500 KB): loaded only when an interview starts.
const Live = lazy(() => import('./screens/Live'))

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined)
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined)
  const path = usePath()

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  const userId = session?.user.id
  useEffect(() => {
    if (!userId) return setProfile(undefined)
    supabase.from('profiles').select('*').eq('user_id', userId).maybeSingle()
      .then(({ data }) => setProfile((data as Profile | null) ?? null))
  }, [userId])

  if (session === undefined) return null
  if (!session) return <SignIn />
  if (profile === undefined) return <div className="page"><p className="muted">Loading…</p></div>
  if (profile === null) return <Onboarding userId={session.user.id} email={session.user.email ?? ''} onDone={setProfile} />

  const email = (session.user.email ?? '').toLowerCase()
  const isAdmin = ADMIN_EMAILS.includes(email)
  if (path === '/live') return <Suspense fallback={null}><Live /></Suspense>

  const topicId = path.match(/^\/topic\/([0-9a-f-]+)/)?.[1]
  let screen = <Today profile={profile} />
  if (topicId) screen = <TopicPage topicId={topicId} />
  else if (path === '/episodes') screen = <Episodes userId={profile.user_id} />
  else if (path === '/settings') screen = <Settings profile={profile} email={email} onSaved={setProfile} />
  else if (path === '/admin' && isAdmin) screen = <Admin />

  return (
    <div className="page">
      <Header path={path} isAdmin={isAdmin} />
      {screen}
    </div>
  )
}
