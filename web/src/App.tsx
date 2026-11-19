import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadAtlas } from './data'
import type { AtlasData } from './types'
import MapView from './components/MapView'
import Timeline from './components/Timeline'
import LedgerPanel from './components/LedgerPanel'

export default function App() {
  const [data, setData] = useState<AtlasData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [showKingdoms, setShowKingdoms] = useState(false)

  useEffect(() => {
    loadAtlas().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  const count = data?.ledger.entries.length ?? 0
  const go = useCallback((i: number) => setIdx(Math.max(0, Math.min(count - 1, i))), [count])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go(idx + 1)
      if (e.key === 'ArrowLeft') go(idx - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, idx])

  useEffect(() => {
    if (!playing) return
    if (idx >= count - 1) { setPlaying(false); return }
    const t = setTimeout(() => go(idx + 1), 3500)
    return () => clearTimeout(t)
  }, [playing, idx, count, go])

  const entry = data?.ledger.entries[idx]
  const placeById = useMemo(
    () => new Map(data?.places.features.map((f) => [f.properties.id, f]) ?? []),
    [data],
  )

  if (error) return <div className="splash">資料載入失敗：{error}（請先執行 pipeline 產生 web/public/data）</div>
  if (!data || !entry) return <div className="splash">載入中…</div>

  return (
    <div className="app">
      <header className="topbar">
        <h1>史記地圖 <span>· 跟着陸遷的賬本看秦末楚漢（前209–前202）</span></h1>
        <label className="toggle">
          <input type="checkbox" checked={showKingdoms} onChange={(e) => setShowKingdoms(e.target.checked)} />
          十八王都城（前206）
        </label>
      </header>
      <main className="split">
        <MapView data={data} idx={idx} onSelect={go} showKingdoms={showKingdoms} />
        <LedgerPanel data={data} entry={entry} placeById={placeById} />
      </main>
      <Timeline
        data={data}
        idx={idx}
        onSelect={go}
        playing={playing}
        onTogglePlay={() => { if (idx >= count - 1) go(0); setPlaying((p) => !p) }}
      />
    </div>
  )
}
