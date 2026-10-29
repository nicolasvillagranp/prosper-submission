import { Brand } from '../components/Header'
import ProfileForm from '../components/ProfileForm'
import type { Profile } from '../lib/types'

export default function Onboarding({ userId, email, onDone }: { userId: string; email: string; onDone: (p: Profile) => void }) {
  return (
    <div className="page">
      <header className="header">
        <Brand />
        <span className="muted">{email}</span>
      </header>
      <div className="stack">
        <h1>What should we talk about every morning?</h1>
        <p className="muted">Tell us once. Your first edition will be ready a few minutes after you finish, then every morning at 6:00.</p>
      </div>
      <ProfileForm userId={userId} submitLabel="Prepare my first topics" onSaved={onDone} />
    </div>
  )
}
