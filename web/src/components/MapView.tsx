import { useEffect, useRef } from 'react'
import maplibregl, { type GeoJSONSource, type Map as MLMap } from 'maplibre-gl'
import type { FeatureCollection, LineString, Point } from 'geojson'
import type { AtlasData } from '../types'

const BASEMAP: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-saturation': -0.8, 'raster-opacity': 0.75 } },
  ],
}

interface Props { data: AtlasData; idx: number; onSelect: (i: number) => void; showKingdoms: boolean }

export default function MapView({ data, idx, onSelect, showKingdoms }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<MLMap | null>(null)
  const ready = useRef(false)
  const stopMarkers = useRef<maplibregl.Marker[]>([])
  const kingdomMarkers = useRef<maplibregl.Marker[]>([])
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  const entries = data.ledger.entries
  const line = data.route.features.find((f) => f.geometry.type === 'LineString')!.geometry as LineString

  useEffect(() => {
    const m = new maplibregl.Map({ container: el.current!, style: BASEMAP, center: [113.5, 34.3], zoom: 5.2 })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')
    map.current = m
    m.on('load', () => {
      m.addSource('places', { type: 'geojson', data: data.places })
      m.addLayer({
        id: 'places', type: 'circle', source: 'places',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['get', 'mentions_year'], 0, 0, 1, 4, 20, 14],
          'circle-color': '#8a5a2b', 'circle-opacity': 0.35,
          'circle-stroke-color': '#8a5a2b', 'circle-stroke-width': 1,
        },
      })
      m.addSource('route-all', { type: 'geojson', data: { type: 'Feature', geometry: line, properties: {} } })
      m.addLayer({ id: 'route-all', type: 'line', source: 'route-all',
        paint: { 'line-color': '#b23a2e', 'line-width': 2, 'line-opacity': 0.25, 'line-dasharray': [2, 2] } })
      m.addSource('route-done', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: {} } })
      m.addLayer({ id: 'route-done', type: 'line', source: 'route-done',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#b23a2e', 'line-width': 3.5 } })

      m.on('click', 'places', (e) => {
        const f = e.features?.[0]
        if (!f) return
        const p = f.properties as Record<string, string | number>
        const years = JSON.parse(String(p.mentions_by_year)) as Record<string, number>
        const yearsText = Object.entries(years).sort((a, b) => +b[0] - +a[0]).map(([y, n]) => `前${y}：${n}`).join('；')
        new maplibregl.Popup({ closeButton: false })
          .setLngLat((f.geometry as Point).coordinates as [number, number])
          .setHTML(`<b>${p.name}</b><br/>今：${p.modern}<br/>當年提及 ${p.mentions_year} 次<br/><small>${yearsText}</small><br/><small>座標精度：${p.precision}</small>`)
          .addTo(m)
      })
      m.on('mouseenter', 'places', () => { m.getCanvas().style.cursor = 'pointer' })
      m.on('mouseleave', 'places', () => { m.getCanvas().style.cursor = '' })

      const placeCoord = new Map(data.places.features.map((f) => [f.properties.id, f.geometry.coordinates]))
      const seen = new Map<string, number>()
      stopMarkers.current = entries.map((e, i) => {
        const n = seen.get(e.place_id) ?? 0
        seen.set(e.place_id, n + 1)
        const node = document.createElement('button')
        node.className = 'stop'
        node.textContent = String(e.seq)
        node.title = e.title
        node.onclick = (ev) => { ev.stopPropagation(); onSelectRef.current(i) }
        return new maplibregl.Marker({ element: node, offset: [n * 18, -n * 4] })
          .setLngLat(placeCoord.get(e.place_id) as [number, number]).addTo(m)
      })
      ready.current = true
      m.fire('atlas-ready')
    })
    return () => { m.remove(); map.current = null; ready.current = false }
  }, [data, entries, line])

  useEffect(() => {
    const m = map.current
    if (!m) return
    const apply = () => {
      const entry = entries[idx]
      const year = String(entry.year_bce)
      const places: FeatureCollection<Point> = {
        ...data.places,
        features: data.places.features.map((f) => ({
          ...f, properties: { ...f.properties, mentions_year: f.properties.mentions_by_year[year] ?? 0 },
        })),
      }
      ;(m.getSource('places') as GeoJSONSource).setData(places)
      ;(m.getSource('route-done') as GeoJSONSource).setData({
        type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: line.coordinates.slice(0, idx + 1) },
      })
      stopMarkers.current.forEach((mk, i) => {
        const node = mk.getElement()
        node.classList.toggle('current', i === idx)
        node.classList.toggle('future', i > idx)
      })
      m.flyTo({ center: line.coordinates[idx] as [number, number], zoom: Math.max(m.getZoom(), 5.6), speed: 0.8 })
    }
    if (ready.current) apply()
    else m.once('atlas-ready', apply)
  }, [idx, data, entries, line])

  useEffect(() => {
    const m = map.current
    if (!m) return
    const apply = () => {
      kingdomMarkers.current.forEach((k) => k.remove())
      kingdomMarkers.current = []
      if (!showKingdoms) return
      for (const f of data.places.features) {
        if (!f.properties.kingdom_206) continue
        const node = document.createElement('div')
        node.className = 'kingdom'
        node.innerHTML = `<span>${f.properties.kingdom_206}</span>${f.properties.king_206}·${f.properties.name}`
        kingdomMarkers.current.push(new maplibregl.Marker({ element: node, anchor: 'left', offset: [8, 0] })
          .setLngLat(f.geometry.coordinates as [number, number]).addTo(m))
      }
    }
    if (ready.current) apply()
    else m.once('atlas-ready', apply)
  }, [showKingdoms, data])

  return <div className="map" ref={el} data-testid="map" />
}
