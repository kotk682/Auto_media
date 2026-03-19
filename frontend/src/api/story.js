import { useSettingsStore } from '../stores/settings.js'

function getHeaders() {
  const settings = useSettingsStore()
  const headers = { 'Content-Type': 'application/json' }
  if (settings.apiKey) headers['X-LLM-API-Key'] = settings.apiKey
  if (settings.llmBaseUrl) headers['X-LLM-Base-URL'] = settings.llmBaseUrl
  if (settings.provider) headers['X-LLM-Provider'] = settings.provider
  return headers
}

function getUrl(path) {
  const settings = useSettingsStore()
  const base = settings.backendUrl ? settings.backendUrl.replace(/\/$/, '') : ''
  return `${base}/api/v1/story${path}`
}

export async function analyzeIdea(idea, genre, tone) {
  const res = await fetch(getUrl('/analyze-idea'), {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ idea, genre, tone }),
  })
  if (!res.ok) throw new Error(`请求失败 (${res.status})`)
  return res.json()
}

export async function generateOutline(storyId, selectedSetting) {
  const res = await fetch(getUrl('/generate-outline'), {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ story_id: storyId, selected_setting: selectedSetting }),
  })
  if (!res.ok) throw new Error(`请求失败 (${res.status})`)
  return res.json()
}

export async function refineStory(storyId, changeType, changeSummary) {
  const res = await fetch(getUrl('/refine'), {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ story_id: storyId, change_type: changeType, change_summary: changeSummary }),
  })
  if (!res.ok) return null
  return res.json()
}

export async function streamChat(storyId, message, onChunk, onDone, onError) {
  let res
  try {
    res = await fetch(getUrl('/chat'), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ story_id: storyId, message }),
    })
  } catch (e) {
    onError?.(e.message); return
  }
  if (!res.ok) { onError?.(`请求失败 (${res.status})`); return }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') { onDone(); return }
        if (payload.startsWith('[ERROR]')) { onError?.(payload.slice(8)); return }
        onChunk(payload)
      }
    }
  } catch (e) {
    onError?.(e.message); return
  }
  onDone()
}

export async function streamScript(storyId, onScene, onDone, onError) {
  let res
  try {
    res = await fetch(getUrl('/generate-script'), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ story_id: storyId }),
    })
  } catch (e) {
    onError?.(e.message); return
  }
  if (!res.ok) { onError?.(`请求失败 (${res.status})`); return }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6).trim()
        if (payload === '[DONE]') { onDone(); return }
        if (payload.startsWith('[ERROR]')) { onError?.(payload.slice(8).trim()); return }
        try { onScene(JSON.parse(payload)) } catch { onError?.('数据解析失败'); return }
      }
    }
    if (buffer.startsWith('data: ')) {
      const payload = buffer.slice(6).trim()
      if (payload && payload !== '[DONE]') {
        try { onScene(JSON.parse(payload)) } catch {}
      }
    }
  } catch (e) {
    onError?.(e.message); return
  }
  onDone()
}
