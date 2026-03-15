const BASE = ''

export async function getHealth() {
  const r = await fetch(`${BASE}/health`)
  return r.json()
}

export async function getEvents() {
  const r = await fetch(`${BASE}/events`)
  return r.json() as Promise<any[]>
}

export async function getTimeline() {
  const r = await fetch(`${BASE}/timeline`)
  return r.json() as Promise<any[]>
}

export async function getGraph() {
  const r = await fetch(`${BASE}/graph`)
  return r.json() as Promise<{ nodes: any[]; edges: any[] }>
}

export async function getAlerts() {
  const r = await fetch(`${BASE}/alerts`)
  return r.json() as Promise<any[]>
}

export async function loadFixtures() {
  const r = await fetch(`${BASE}/fixtures/load`, { method: 'POST' })
  return r.json()
}
