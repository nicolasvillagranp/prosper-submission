import { useEffect, useState } from 'react'

import { supabase } from './supabase'

// Topic covers live in Storage at recordings/<user_id>/covers/<topic_id>.jpg (pipeline/covers.py).
// The page asks for short-lived signed URLs; a topic without a cover simply gets none.

export function useCovers(topics: { id: string }[], userId: string): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({})
  const ids = topics.map((t) => t.id).join(',')
  useEffect(() => {
    if (!ids || !userId) return
    let alive = true
    const list = ids.split(',')
    supabase.storage.from('recordings').createSignedUrls(list.map((id) => `${userId}/covers/${id}.jpg`), 3600)
      .then(({ data }) => {
        if (!alive || !data) return
        const found: Record<string, string> = {}
        data.forEach((d, i) => { if (d.signedUrl && !d.error) found[list[i]] = d.signedUrl })
        setUrls(found)
      })
    return () => { alive = false }
  }, [ids, userId])
  return urls
}
