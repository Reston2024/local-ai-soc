/**
 * Design tokens — single source of truth for severity colours,
 * nav metadata, and palette-level constants.
 *
 * Import in any .svelte or .ts file:
 *   import { SEV, sev, NAV_GROUPS } from '$lib/tokens'
 */

// ---------------------------------------------------------------------------
// Severity palette
// ---------------------------------------------------------------------------

export const SEV = {
  critical: {
    fg:   '#ef4444',
    bg:   'rgba(239,68,68,0.12)',
    br:   'rgba(239,68,68,0.30)',
    ring: 'rgba(239,68,68,0.20)',
    label: 'Critical',
  },
  high: {
    fg:   '#f97316',
    bg:   'rgba(249,115,22,0.12)',
    br:   'rgba(249,115,22,0.30)',
    ring: 'rgba(249,115,22,0.20)',
    label: 'High',
  },
  medium: {
    fg:   '#eab308',
    bg:   'rgba(234,179,8,0.12)',
    br:   'rgba(234,179,8,0.30)',
    ring: 'rgba(234,179,8,0.20)',
    label: 'Medium',
  },
  low: {
    fg:   '#22c55e',
    bg:   'rgba(34,197,94,0.12)',
    br:   'rgba(34,197,94,0.30)',
    ring: 'rgba(34,197,94,0.20)',
    label: 'Low',
  },
  info: {
    fg:   '#3b82f6',
    bg:   'rgba(59,130,246,0.12)',
    br:   'rgba(59,130,246,0.30)',
    ring: 'rgba(59,130,246,0.20)',
    label: 'Info',
  },
} as const

export type SevKey = keyof typeof SEV

/** Return the SEV token for a severity string (case-insensitive, defaults to info). */
export function sev(s: string | null | undefined): (typeof SEV)[SevKey] {
  const k = ((s ?? 'info').toLowerCase()) as SevKey
  return SEV[k] ?? SEV.info
}

// ---------------------------------------------------------------------------
// Navigation metadata
// ---------------------------------------------------------------------------

export type ViewId =
  | 'overview' | 'detections' | 'investigation' | 'events' | 'graph' | 'query' | 'ingest'
  | 'intel' | 'hunting' | 'playbooks' | 'reports' | 'assets' | 'provenance'
  | 'recommendations' | 'settings' | 'map' | 'attack-coverage' | 'atomics' | 'anomaly'
  | 'performance'

export interface NavItem {
  id: ViewId
  label: string
  group: string
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Monitor',
    items: [
      { id: 'overview',     label: 'Overview',         group: 'Monitor' },
      { id: 'detections',   label: 'Detections',       group: 'Monitor' },
      { id: 'events',       label: 'Events',            group: 'Monitor' },
      { id: 'assets',       label: 'Assets',            group: 'Monitor' },
    ],
  },
  {
    label: 'Investigate',
    items: [
      { id: 'investigation', label: 'Investigation',   group: 'Investigate' },
      { id: 'graph',         label: 'Attack Graph',    group: 'Investigate' },
      { id: 'provenance',    label: 'Provenance',      group: 'Investigate' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { id: 'intel',           label: 'Threat Intel',     group: 'Intelligence' },
      { id: 'attack-coverage', label: 'ATT&CK Coverage',  group: 'Intelligence' },
      { id: 'hunting',         label: 'Hunting',           group: 'Intelligence' },
      { id: 'map',             label: 'Threat Map',        group: 'Intelligence' },
      { id: 'atomics',         label: 'Atomics',           group: 'Intelligence' },
      { id: 'anomaly',         label: 'Anomaly Profiles',  group: 'Intelligence' },
    ],
  },
  {
    label: 'Respond',
    items: [
      { id: 'playbooks',        label: 'Playbooks',        group: 'Respond' },
      { id: 'recommendations',  label: 'Recommendations',  group: 'Respond' },
      { id: 'reports',          label: 'Reports',          group: 'Respond' },
    ],
  },
  {
    label: 'Platform',
    items: [
      { id: 'performance', label: 'Performance',  group: 'Platform' },
      { id: 'query',       label: 'AI Query',     group: 'Platform' },
      { id: 'ingest',      label: 'Ingest',       group: 'Platform' },
      { id: 'settings',    label: 'Settings',     group: 'Platform' },
    ],
  },
]

/** Flat list of all nav items for quick lookup. */
export const ALL_NAV: NavItem[] = NAV_GROUPS.flatMap(g => g.items)
