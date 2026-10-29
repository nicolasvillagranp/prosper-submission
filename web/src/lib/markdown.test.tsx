import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { Markdown } from './markdown'

describe('Markdown', () => {
  it('renders headings, lists and bold', () => {
    const html = renderToStaticMarkup(<Markdown text={'# Title\n## Angles\n- one **big** idea\n- two\n\n1. first?\n2. second?\nPlain line.'} />)
    expect(html).toBe(
      '<div class="markdown"><h3>Angles</h3><ul><li>one <strong>big</strong> idea</li><li>two</li></ul>'
      + '<ol><li>first?</li><li>second?</li></ol><p>Plain line.</p></div>',
    )
  })

  it('never turns text into HTML', () => {
    expect(renderToStaticMarkup(<Markdown text={'<img src=x onerror=alert(1)>'} />)).toContain('&lt;img')
  })
})
