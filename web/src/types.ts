import type { Feature, FeatureCollection, LineString, Point } from 'geojson'

export interface Goods { item: string; action: string; qty: string; amount: string }

export interface LedgerEntry {
  id: string; seq: number; year_bce: number; month: number | null; sort_key: number
  place_id: string; event_id: string | null; title: string; text: string; goods: Goods[]
}

export interface Ledger { merchant: string; fictional: boolean; note: string; entries: LedgerEntry[] }

export interface Citation { passage_id: string; work: string; juan: number; year_label: string; year_bce: number; snippet: string }

export interface HistEvent {
  id: string; title: string; year_bce: number; month: number | null; sort_key: number
  place_id: string; keywords: string[]; summary: string; citations: Citation[]
}

export interface Passage {
  id: string; work: string; juan: number; year_bce: number; year_label: string; entry_no: number
  kind: 'narrative' | 'commentary'; text: string; months: number[]; places: Record<string, number>; date_source: string
}

export interface PlaceProps {
  id: string; name: string; kind: string; modern: string; precision: string; chgis_id: string | null; geo_note: string
  mentions_by_year: Record<string, number>; mentions_total: number
  kingdom_206: string | null; king_206: string | null
}

export type PlaceFC = FeatureCollection<Point, PlaceProps>
export type RouteFC = FeatureCollection<LineString | Point>
export type PlaceFeature = Feature<Point, PlaceProps>

export interface AtlasData {
  ledger: Ledger; events: HistEvent[]; passages: Passage[]; places: PlaceFC; route: RouteFC
}
