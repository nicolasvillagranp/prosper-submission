import ProfileForm from '../components/ProfileForm'
import { navigate } from '../lib/router'
import { supabase } from '../lib/supabase'
import type { Profile } from '../lib/types'

export default function Settings({ profile, email, onSaved }: { profile: Profile; email: string; onSaved: (p: Profile) => void }) {
  async function signOut() {
    await supabase.auth.signOut()
    navigate('/')
  }
  return (
    <>
      <div className="stack">
        <h1>Settings</h1>
        <p className="muted">The same preferences you chose at sign-up. Changes apply from the next morning's topics.</p>
      </div>
      <ProfileForm userId={profile.user_id} initial={profile} submitLabel="Save changes" onSaved={onSaved} />
      <section className="card">
        <div className="row between">
          <div className="stack" style={{ gap: 4 }}>
            <h2>Account</h2>
            <p className="muted">Signed in as {email}</p>
          </div>
          <button type="button" className="btn" onClick={signOut}>Sign out</button>
        </div>
      </section>
    </>
  )
}
