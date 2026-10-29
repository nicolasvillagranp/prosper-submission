// The internal engagement dashboard. All numbers are mocked on purpose (docs/design-research.md):
// the app doesn't record topic opens or briefing play-through yet; that needs an events table.

const KPIS = [
  ['Weekly active users', '16 of 20', '2 fewer than last week'],
  ['Daily habit', '68%', 'of users open a topic on a given day'],
  ['Briefing listened', '78%', 'average share of the audio played'],
  ['Interview time', '14 min', 'per active user per week'],
]

const ALERTS = [
  ['Briefing → interview is the weakest step: 27%', 'It was 34% last week. Check whether the invitation at the end of the briefing is landing.'],
  ["4 users haven't opened a topic in 3+ days", 'Before this week they opened one almost every day. Worth a check-in or a look at their topics.'],
  ['6 interviews ended in under a minute', 'Up from 2 the week before. Possible turn-taking or audio problems: read those transcripts.'],
]

// [step, count, previous step's count]
const FUNNEL: [string, number, number][] = [
  ['Opened a topic', 196, 280],
  ['Listened to half the briefing or more', 152, 196],
  ['Started an interview', 41, 152],
  ['Recorded an episode (5+ min)', 30, 41],
]

const DAILY = [11, 12, 14, 13, 15, 12, 13, 15, 16, 15, 14, 13, 12, 11]

const TOPICS = [
  ['AI agents at work', '64', '84%', '31%', '11 min'],
  ['World models', '58', '81%', '29%', '13 min'],
  ['AI and jobs', '55', '76%', '22%', '9 min'],
  ['EU AI regulation', '41', '69%', '17%', '8 min'],
]

export default function Admin() {
  const pcts = FUNNEL.map(([, n, prev]) => Math.round((n / prev) * 100))
  const weakest = Math.min(...pcts.slice(1))
  return (
    <>
      <div className="row between">
        <div className="stack" style={{ gap: 4 }}>
          <span className="muted">Internal · admins only</span>
          <h1>Are users engaging?</h1>
        </div>
        <span className="badge">Mocked data</span>
      </div>

      <div className="kpis">
        {KPIS.map(([label, value, note]) => (
          <div key={label} className="kpi">
            <span className="muted small">{label}</span>
            <strong>{value}</strong>
            <span className="small">{note}</span>
          </div>
        ))}
      </div>

      <section className="card" aria-label="Needs attention">
        <h3>Needs attention</h3>
        {ALERTS.map(([title, detail]) => (
          <div key={title} className="alert">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8a4b00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" role="img" aria-label="Warning" style={{ flex: '0 0 auto' }}>
              <path d="M12 3 2 20h20z" /><path d="M12 10v4" /><path d="M12 17h.01" />
            </svg>
            <div className="stack" style={{ gap: 2 }}>
              <strong style={{ fontSize: 15 }}>{title}</strong>
              <span style={{ fontSize: 14, color: 'var(--ink-2)' }}>{detail}</span>
            </div>
          </div>
        ))}
      </section>

      <div className="row" style={{ alignItems: 'stretch', gap: 14 }}>
        <section className="card" style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div>
            <h3>Where people drop off</h3>
            <p className="muted small">Each step as a % of the step before it. The weakest step is the one to fix first.</p>
          </div>
          {FUNNEL.map(([label, n, prev], i) => {
            const weak = i > 0 && pcts[i] === weakest
            return (
              <div key={label} className="stack" style={{ gap: 4 }}>
                <div className="row between" style={{ fontSize: 14 }}>
                  <span>{label} {weak && <strong style={{ color: 'var(--warn-ink)' }}>· weakest step</strong>}</span>
                  <span><strong>{pcts[i]}%</strong> <span className="muted">· {n} of {prev}{i === 0 ? ' days with topics' : ''}</span></span>
                </div>
                <div className="bar"><div style={{ width: `${pcts[i]}%`, background: weak ? '#b45309' : undefined }} /></div>
              </div>
            )
          })}
        </section>
        <section className="card" style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div>
            <h3>Users who opened a topic, per day</h3>
            <p className="muted small">Out of 20 invited users. Falling since Oct 22.</p>
          </div>
          <div className="columns" role="img" aria-label="Users who opened a topic per day over 14 days: up to 16, now 11">
            {DAILY.map((n, i) => <div key={i} style={{ height: `${(n / 20) * 100}%` }} title={`${n} users`} />)}
          </div>
          <div className="row between muted small"><span>14 days ago</span><span>Today · 11</span></div>
        </section>
      </div>

      <section className="card">
        <h3>Which topics hook people</h3>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr><th>Theme</th><th>Opened</th><th>Briefing listened</th><th>Went on to interview</th><th>Avg. interview</th></tr>
            </thead>
            <tbody>
              {TOPICS.map((r) => <tr key={r[0]}>{r.map((c, i) => <td key={i}>{c}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
