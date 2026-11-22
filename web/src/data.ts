import type { AtlasData } from './types'

const base = `${import.meta.env.BASE_URL}data/`

async function get<T>(name: string): Promise<T> {
  const res = await fetch(base + name)
  if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export async function loadAtlas(): Promise<AtlasData> {
  const [ledger, events, passages, places, route, divergences] = await Promise.all([
    get<AtlasData['ledger']>('luqian_ledger.json'),
    get<AtlasData['events']>('events.json'),
    get<AtlasData['passages']>('passages.json'),
    get<AtlasData['places']>('places.geojson'),
    get<AtlasData['route']>('luqian_route.geojson'),
    get<AtlasData['divergences']>('yanyi_divergences.json'),
  ])
  ledger.entries.sort((a, b) => a.seq - b.seq)
  return { ledger, events, passages, places, route, divergences }
}

const CN = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']

export function monthName(m: number | null): string {
  if (!m) return ''
  return m === 1 ? '正月' : `${CN[m]}月`
}

export function reignYear(yearBce: number): string {
  if (yearBce >= 207) return `秦二世${yearBce === 209 ? '元' : CN[210 - yearBce]}年`
  return `漢高帝${yearBce === 206 ? '元' : CN[207 - yearBce]}年`
}

export function dateLabel(yearBce: number, month: number | null): string {
  return `前${yearBce}年 · ${reignYear(yearBce)}${monthName(month)}`
}

export const YANYI = '前漢演義'

export function sourceLabel(work: string, juan: number): string {
  return work === YANYI ? `《${work}》第${juan}回` : `《${work}》卷${juan}`
}

const PRECISION: Record<string, string> = { chgis: 'CHGIS V6', chgis_adjacent: 'CHGIS V6（鄰近年份）', approx: '估計' }

export function precisionLabel(p: string): string {
  return PRECISION[p] ?? p
}
