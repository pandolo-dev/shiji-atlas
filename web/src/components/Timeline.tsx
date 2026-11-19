import type { AtlasData } from '../types'
import { dateLabel } from '../data'

interface Props { data: AtlasData; idx: number; onSelect: (i: number) => void; playing: boolean; onTogglePlay: () => void }

const MIN = -209
const MAX = -202 + 11 / 12

export default function Timeline({ data, idx, onSelect, playing, onTogglePlay }: Props) {
  const x = (k: number) => `${((k - MIN) / (MAX - MIN)) * 100}%`
  const entries = data.ledger.entries
  const years = [209, 208, 207, 206, 205, 204, 203, 202]
  return (
    <footer className="timeline">
      <div className="controls">
        <button onClick={() => onSelect(idx - 1)} disabled={idx === 0} aria-label="上一條">◀</button>
        <button onClick={onTogglePlay} aria-label={playing ? '暫停' : '播放'}>{playing ? '❚❚' : '▶'}</button>
        <button onClick={() => onSelect(idx + 1)} disabled={idx === entries.length - 1} aria-label="下一條">▶|</button>
        <span className="now">{dateLabel(entries[idx].year_bce, entries[idx].month)}</span>
      </div>
      <div className="track">
        {years.map((y) => (
          <div key={y} className="year" style={{ left: x(-y) }}><span>前{y}</span></div>
        ))}
        {data.events.map((e) => (
          <div key={e.id} className="event" style={{ left: x(e.sort_key) }} title={`${dateLabel(e.year_bce, e.month)} ${e.title}`} />
        ))}
        <div className="progress" style={{ width: x(entries[idx].sort_key) }} />
        {entries.map((e, i) => (
          <button
            key={e.id}
            className={`tick${i === idx ? ' current' : ''}`}
            style={{ left: x(e.sort_key), top: i % 2 ? 34 : 14 }}
            onClick={() => onSelect(i)}
            title={`${dateLabel(e.year_bce, e.month)} ${e.title}`}
          >
            {e.seq}
          </button>
        ))}
      </div>
    </footer>
  )
}
