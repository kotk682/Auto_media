function trimTrailingSlash(value = '') {
  return String(value || '').trim().replace(/\/$/, '')
}

export function resolveBackendBaseUrl(configuredBackendUrl = '', { preferRelativeInDev = false } = {}) {
  const configured = trimTrailingSlash(configuredBackendUrl)
  if (configured) return configured

  if (import.meta.env.DEV) {
    return ''
  }

  if (typeof window !== 'undefined' && window.location?.origin) {
    return trimTrailingSlash(window.location.origin)
  }

  return ''
}

export function resolveBackendHealthUrl(configuredBackendUrl = '') {
  const base = resolveBackendBaseUrl(configuredBackendUrl, { preferRelativeInDev: true })
  return base ? `${base}/health` : '/health'
}

export function resolveBackendMediaUrl(path, configuredBackendUrl = '') {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) return path

  const base = resolveBackendBaseUrl(configuredBackendUrl, { preferRelativeInDev: true })
  return base ? `${base}${path}` : path
}
