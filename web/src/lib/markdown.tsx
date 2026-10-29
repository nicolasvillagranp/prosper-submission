import type { ReactNode } from 'react'

// Just enough markdown for the study guide: headings, bullet and numbered lists, **bold**.
// Built as React elements (never innerHTML), so text from the LLM can't inject markup.

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  const flush = () => {
    if (!list) return
    const items = list.items.map((t, i) => <li key={i}>{inline(t)}</li>)
    blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>)
    list = null
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = line.match(/^[-*] (.*)/)
    const numbered = line.match(/^\d+\. (.*)/)
    if (bullet || numbered) {
      const ordered = Boolean(numbered)
      if (!list || list.ordered !== ordered) {
        flush()
        list = { ordered, items: [] }
      }
      list.items.push((bullet ?? numbered)![1])
      continue
    }
    flush()
    if (!line) continue
    const heading = line.match(/^(#{1,3}) (.*)/)
    if (heading) {
      blocks.push(heading[1].length === 1 ? null : <h3 key={blocks.length}>{inline(heading[2])}</h3>)
    } else {
      blocks.push(<p key={blocks.length}>{inline(line)}</p>)
    }
  }
  flush()
  return <div className="markdown">{blocks}</div>
}
