import type { AtlasData, LedgerEntry, PlaceFeature } from '../types'
import { dateLabel, precisionLabel } from '../data'

interface Props { data: AtlasData; entry: LedgerEntry; placeById: Map<string, PlaceFeature> }

function highlight(text: string, kws: string[]) {
  const kw = kws.find((k) => text.includes(k))
  if (!kw) return text
  const i = text.indexOf(kw)
  return <>{text.slice(0, i)}<mark>{kw}</mark>{text.slice(i + kw.length)}</>
}

export default function LedgerPanel({ data, entry, placeById }: Props) {
  const place = placeById.get(entry.place_id)?.properties
  const event = data.events.find((e) => e.id === entry.event_id)
  const sameYearPlace = data.passages.filter(
    (p) => p.kind === 'narrative' && p.year_bce === entry.year_bce && p.places[entry.place_id],
  )
  const yearEvents = data.events.filter((e) => e.year_bce === entry.year_bce)

  return (
    <aside className="panel">
      <section className="card ledger">
        <div className="meta">
          <span className="seq">第 {entry.seq} 條</span>
          <span>{dateLabel(entry.year_bce, entry.month)}</span>
          <span className="badge" title={data.ledger.note}>虛構</span>
        </div>
        <h2>{entry.title}<small> · {place?.name}</small></h2>
        <p className="ledger-text">{entry.text}</p>
        {entry.goods.length > 0 && (
          <table className="goods">
            <thead><tr><th>貨</th><th>事</th><th>數</th><th>錢</th></tr></thead>
            <tbody>
              {entry.goods.map((g, i) => (
                <tr key={i}><td>{g.item}</td><td>{g.action}</td><td>{g.qty}</td>
                  <td className={g.amount.startsWith('-') ? 'loss' : 'gain'}>{g.amount}</td></tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="place-note">今地：{place?.modern}（座標：{place && precisionLabel(place.precision)}）<br />{place?.geo_note}</p>
      </section>

      {event && (
        <section className="card event-card">
          <h3>史事：{event.title}</h3>
          <p>{event.summary}</p>
          <ul className="cites">
            {event.citations.map((c) => (
              <li key={c.passage_id}>
                <span className="src">《{c.work}》卷{c.juan}·{c.year_label}</span>
                <span className="snip">{highlight(c.snippet, event.keywords)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h3>前{entry.year_bce}年大事</h3>
        <ul className="year-events">
          {yearEvents.map((e) => (
            <li key={e.id} className={e.id === entry.event_id ? 'active' : ''}>
              {dateLabel(e.year_bce, e.month).split(' · ')[1]}{' '}{e.title}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>同年提及「{place?.name}」的原文（{sameYearPlace.length}）</h3>
        <ul className="passages">
          {sameYearPlace.slice(0, 6).map((p) => (
            <li key={p.id}>
              <span className="src">《{p.work}》卷{p.juan}{p.work === '資治通鑑' ? `·${p.year_label}·第${p.entry_no}條` : ''}</span>
              <span className="snip">{p.text.length > 160 ? p.text.slice(0, 160) + '…' : p.text}</span>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  )
}
