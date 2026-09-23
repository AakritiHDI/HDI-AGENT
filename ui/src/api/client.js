const BASE = '/api'

export async function fetchConfig() {
  const res = await fetch(`${BASE}/config`)
  if (!res.ok) throw new Error('Failed to fetch config')
  return res.json()
}

export async function fetchSetupStatus() {
  const res = await fetch(`${BASE}/setup/status`)
  if (!res.ok) throw new Error('Failed to fetch setup status')
  return res.json()
}

export async function triggerSetup() {
  const res = await fetch(`${BASE}/setup`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to trigger setup')
  return res.json()
}

export async function fetchSessions() {
  const res = await fetch(`${BASE}/sessions`)
  if (!res.ok) throw new Error('Failed to fetch sessions')
  return res.json()
}

export async function createSession(username) {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username }),
  })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function fetchSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`)
  if (!res.ok) throw new Error('Session not found')
  return res.json()
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete session')
  return res.json()
}

export async function renameSession(sessionId, title) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/rename`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  if (!res.ok) throw new Error('Failed to rename session')
  return res.json()
}

export async function sendMessage(sessionId, message) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw new Error('Failed to send message')
  return res.json()
}