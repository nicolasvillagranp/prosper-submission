import { useEffect, useState } from 'react'

// A tiny router: the path is the state. Vercel serves index.html for every page (vercel.json).

export function navigate(path: string, state?: unknown) {
  window.history.pushState(state ?? null, '', path)
  window.dispatchEvent(new PopStateEvent('popstate', { state }))
  window.scrollTo(0, 0)
}

export function usePath(): string {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const update = () => setPath(window.location.pathname)
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])
  return path
}

/** Click handler for <a href> links that stay inside the app. */
export function goTo(e: React.MouseEvent<HTMLAnchorElement>) {
  if (e.metaKey || e.ctrlKey || e.button !== 0) return
  e.preventDefault()
  navigate(e.currentTarget.getAttribute('href') ?? '/')
}
