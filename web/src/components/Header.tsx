import { goTo } from '../lib/router'

export const BRAND = 'The Daily Interview'

export function Brand() {
  return <a href="/" onClick={goTo} className="brand">{BRAND}</a>
}

const today = () => new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

/** The front page gets a newspaper masthead; every other page a slim header. */
export default function Header({ path, isAdmin }: { path: string; isAdmin: boolean }) {
  const links = [
    { href: '/', label: 'Today', active: path === '/' || path.startsWith('/topic/') },
    { href: '/episodes', label: 'My episodes', active: path === '/episodes' },
    { href: '/settings', label: 'Settings', active: path === '/settings' },
    ...(isAdmin ? [{ href: '/admin', label: 'Dashboard', active: path === '/admin' }] : []),
  ]
  const nav = (
    <nav className="nav" aria-label="Main">
      {links.map((l) => (
        <a key={l.href} href={l.href} onClick={goTo} className={l.active ? 'active' : ''} aria-current={l.active ? 'page' : undefined}>
          {l.label}
        </a>
      ))}
    </nav>
  )
  if (path === '/') {
    return (
      <header className="masthead">
        <div className="row between" style={{ width: '100%' }}>
          <span className="muted small" style={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>{today()}</span>
          {nav}
        </div>
        <span className="title">{BRAND}</span>
        <span className="muted">Five stories picked for you · listen, then talk to the expert</span>
      </header>
    )
  }
  return (
    <header className="header" style={{ borderBottom: '1px solid var(--line-strong)', paddingBottom: 12 }}>
      <Brand />
      {nav}
    </header>
  )
}
