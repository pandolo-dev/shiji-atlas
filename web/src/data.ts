import type { AtlasData } from './types'

const base = `${import.meta.env.BASE_URL}data/`

async function get<T>(name: string): Promise<T> {
  const res = await fetch(base + name)
  if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export async function loadAtlas(): Promise<AtlasData> {
  const [ledger, events, passages, places, route] = await Promise.all([
    get<AtlasData['ledger']>('luqian_ledger.json'),
    get<AtlasData['events']>('events.json'),
    get<AtlasData['passages']>('passages.json'),
    get<AtlasData['places']>('places.geojson'),
    get<AtlasData['route']>('luqian_route.geojson'),
  ])
  ledger.entries.sort((a, b) => a.seq - b.seq)
  return { ledger, events, passages, places, route }
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
