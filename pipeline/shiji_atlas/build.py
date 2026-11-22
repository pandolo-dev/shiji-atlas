"""Build JSON/GeoJSON + PostGIS seed for the Chu–Han slice (209–202 BCE)."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import shiji, tongjian, yanyi
from .gazetteer import Gazetteer
from .numerals import sort_key

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CURATED = ROOT / "data" / "curated"
OUT = ROOT / "data" / "out"
WEB = ROOT / "web" / "public" / "data"
SEED = ROOT / "db" / "seed.sql"

YEAR_MIN, YEAR_MAX = 202, 209  # BCE, inclusive

TONGJIAN = [7, 8, 9, 10, 11]
SHIJI = {7: "項羽本紀", 8: "高祖本紀", 48: "陳涉世家"}
YANYI = range(9, 33)  # 前漢演義 第九回 大澤鄉 … 第三十二回 即帝位


def load_passages(gaz: Gazetteer) -> list:
    passages = []
    for juan in TONGJIAN:
        passages += tongjian.parse((RAW / f"資治通鑑_卷{juan:03d}.wiki").read_text(), juan)
    for juan, title in SHIJI.items():
        passages += shiji.parse((RAW / f"史記_卷{juan:03d}.wiki").read_text(), juan, title)
    passages += yanyi.parse([(n, (RAW / f"前漢演義_第{n:03d}回.wiki").read_text()) for n in YANYI])
    for p in passages:
        p.places = gaz.count(p.text)
    return passages


def in_slice(p) -> bool:
    return YEAR_MIN <= p.year_bce <= YEAR_MAX


def snippet(text: str, kw: str, before: int = 30, after: int = 70) -> str:
    i = text.find(kw)
    s, e = max(0, i - before), min(len(text), i + len(kw) + after)
    return ("…" if s else "") + text[s:e].replace("\n", "") + ("…" if e < len(text) else "")


CARRIED_WINDOW = 1  # years an event may differ from the running year to re-date a carried paragraph


def keywords(ev: dict, p) -> list[str]:
    """前漢演義 is vernacular, so an event may list separate "yanyi_keywords" for it."""
    return ev.get("yanyi_keywords", ev["keywords"]) if p.work == yanyi.WORK else ev["keywords"]


def matches(ev: dict, p) -> bool:
    return all(k in p.text for k in keywords(ev, p))


def sequences(passages: list) -> list[list]:
    """Documents dated by markers + carry: each 史記 chapter, and 前漢演義 as one continuous text."""
    groups: dict[tuple, list] = {}
    for p in passages:
        if p.work == "史記":
            groups.setdefault((p.work, p.juan), []).append(p)
        elif p.work == yanyi.WORK:
            groups.setdefault((p.work,), []).append(p)
    return list(groups.values())


def date_carried(events: list[dict], passages: list) -> None:
    """Date carried 史記/前漢演義 paragraphs in strict document order.

    A carried paragraph inherits the running year (its preceding dated paragraph).
    It is re-dated to an event it mentions only if that event is listed for it in
    events.json "passages", or it lies within CARRIED_WINDOW of the running year
    and between the running year and the next marker (if any). Rejected matches are flagged.
    """
    for seq in sequences(passages):
        nxt: list[int | None] = [None] * len(seq)
        for i in range(len(seq) - 2, -1, -1):
            q = seq[i + 1]
            nxt[i] = q.year_bce if q.date_source == "marker" else nxt[i + 1]
        run_year, run_label = seq[0].year_bce, seq[0].year_label
        for i, p in enumerate(seq):
            if p.date_source == "marker":
                run_year, run_label = p.year_bce, p.year_label
                continue
            p.year_bce, p.year_label = run_year, run_label
            if p.kind != "narrative":
                continue
            allow = [e for e in events if p.id in e.get("passages", [])]
            cands = allow or [e for e in events
                              if abs(e["year_bce"] - run_year) <= CARRIED_WINDOW and matches(e, p)]
            lo, hi = sorted((run_year, nxt[i])) if nxt[i] is not None else (-9999, 9999)
            ok = allow or [e for e in cands if lo <= e["year_bce"] <= hi]
            if cands and not ok:
                p.date_flag = "anchor_rejected(" + "、".join(e["id"] for e in cands) + ")"
            if ok:
                ev = min(ok, key=lambda e: (abs(e["year_bce"] - run_year), e["sort_key"]))
                p.year_bce = run_year = ev["year_bce"]
                p.year_label = run_label = f"{p.year_label.split('·')[0]}·繫於「{ev['title']}」"
                p.date_source = "event_allowlist" if allow else "event_keyword"


def rejected(p) -> set[str]:
    """Event ids whose keyword anchor date_carried rejected for this passage."""
    m = re.match(r"anchor_rejected\((.*)\)$", p.date_flag)
    return set(m.group(1).split("、")) if m else set()


def link_events(events: list[dict], passages: list) -> None:
    """Cite narrative passages that contain all of an event's keywords.

    資治通鑑 must match the event year, 史記/前漢演義 (dated by date_carried) may be off by
    CARRIED_WINDOW unless that anchor was rejected; ids in an event's "passages" are cited regardless.
    """
    for ev in events:
        allow = set(ev.get("passages", []))
        cites = []
        for p in passages:
            if p.kind != "narrative":
                continue
            slack = 0 if p.work == "資治通鑑" else CARRIED_WINDOW
            if p.id in allow or (abs(p.year_bce - ev["year_bce"]) <= slack and matches(ev, p)
                                 and ev["id"] not in rejected(p)):
                cites.append({"passage_id": p.id, "work": p.work, "juan": p.juan, "year_bce": p.year_bce,
                              "year_label": p.year_label, "snippet": snippet(p.text, keywords(ev, p)[0])})
        ev["citations"] = cites


def flag_contradictions(passages: list) -> list:
    """Flag non-marker 史記/前漢演義 paragraphs dated outside the years of their marker-dated neighbours."""
    flagged = []
    for group in sequences(passages):
        seq = [p for p in group if p.kind == "narrative"]
        for i, p in enumerate(seq):
            if p.date_source == "marker" or p.date_flag:
                continue
            before = next((q.year_bce for q in reversed(seq[:i]) if q.date_source == "marker"), None)
            after = next((q.year_bce for q in seq[i + 1:] if q.date_source == "marker"), None)
            if before is None or after is None:
                continue
            if not min(before, after) <= p.year_bce <= max(before, after):
                p.date_flag = f"contradicts_neighbors({before},{after})"
                flagged.append(p)
    return flagged


def resolve_divergences(doc: dict, passages: list, events: list[dict]) -> tuple[list[dict], list[str]]:
    """Locate each 前漢演義 divergence and its 史記 counter-quotes; quotes outside the corpus stay external."""
    out, errors = [], []
    ev_ids = {e["id"] for e in events}
    corpus = {("史記", j) for j in SHIJI}
    for item in doc["items"]:
        d = dict(item)
        hit = next((p for p in passages if p.work == yanyi.WORK and p.juan == item["chapter"]
                    and item["anchor"] in p.text), None)
        if hit is None:
            errors.append(f"divergence {item['id']}: anchor {item['anchor']!r} not in 第{item['chapter']}回")
            continue
        d.update(passage_id=hit.id, year_bce=hit.year_bce, type_label=doc["types"][item["type"]])
        if item.get("event_id") and item["event_id"] not in ev_ids:
            errors.append(f"divergence {item['id']}: unknown event {item['event_id']}")
        d["sources"] = []
        for src in item["sources"]:
            s = dict(src, passage_id=None)
            if (src["work"], src["juan"]) in corpus:
                p = next((p for p in passages if p.work == src["work"] and p.juan == src["juan"]
                          and src["quote"] in p.text), None)
                if p is None:
                    errors.append(f"divergence {item['id']}: quote {src['quote']!r} not in 《{src['work']}》卷{src['juan']}")
                else:
                    s["passage_id"] = p.id
            d["sources"].append(s)
        out.append(d)
    return out, errors


def point(place, props: dict) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [place.lon, place.lat]},
            "properties": props}


PRECISION = {"matched": "chgis", "adjacent": "chgis_adjacent"}


def apply_chgis(gaz: Gazetteer, doc: dict) -> None:
    """Overlay CHGIS V6 points (see chgis.py) on the curated approximate coordinates."""
    for pid, m in doc["places"].items():
        pl = gaz.places[pid]
        if m["status"] in PRECISION:
            pl.lon, pl.lat = m["lon"], m["lat"]
            pl.precision = PRECISION[m["status"]]
            pl.chgis_id = f"hvd_{m['sys_id']}"
            y0, y1 = (f"前{-y}" if y < 0 else str(y) for y in m["years"])
            note = f"CHGIS V6 {m['name_ft']}（{y0}–{y1}），今{m['pres_loc'].removeprefix('今')}"
            pl.geo_note = note + (f"；{m['reason']}" if m.get("reason") else "")
        else:
            pl.geo_note = m["reason"]


def places_geojson(gaz: Gazetteer, passages: list, kingdoms: list[dict]) -> dict:
    by_year: dict[str, dict[int, int]] = {}
    for p in passages:
        if p.work == yanyi.WORK:  # map mention counts stay source-based; the novel is not evidence
            continue
        for pid, n in p.places.items():
            by_year.setdefault(pid, {}).setdefault(p.year_bce, 0)
            by_year[pid][p.year_bce] += n
    capital_of = {k["capital"]: k for k in kingdoms}
    feats = []
    for pl in gaz.places.values():
        mentions = by_year.get(pl.id, {})
        k = capital_of.get(pl.id)
        feats.append(point(pl, {
            "id": pl.id, "name": pl.name, "kind": pl.kind, "modern": pl.modern,
            "precision": pl.precision, "chgis_id": pl.chgis_id, "geo_note": pl.geo_note,
            "mentions_by_year": {str(y): n for y, n in sorted(mentions.items())},
            "mentions_total": sum(mentions.values()),
            "kingdom_206": k["kingdom"] if k else None, "king_206": k["king"] if k else None,
        }))
    return {"type": "FeatureCollection", "features": feats}


def route_geojson(gaz: Gazetteer, ledger: dict) -> dict:
    entries = sorted(ledger["entries"], key=lambda e: e["seq"])
    coords = [[gaz.places[e["place_id"]].lon, gaz.places[e["place_id"]].lat] for e in entries]
    feats = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
              "properties": {"merchant": ledger["merchant"], "fictional": True}}]
    for e in entries:
        pl = gaz.places[e["place_id"]]
        feats.append(point(pl, {"id": e["id"], "seq": e["seq"], "title": e["title"],
                                "place_id": pl.id, "place": pl.name,
                                "year_bce": e["year_bce"], "month": e["month"]}))
    return {"type": "FeatureCollection", "features": feats}


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return "'" + str(v).replace("'", "''") + "'"


def seed_sql(gaz, passages, events, ledger, kingdoms, divergences=()) -> str:
    lines = ["-- Generated by `python -m shiji_atlas.build`. Do not edit by hand.", "BEGIN;"]
    for pl in gaz.places.values():
        lines.append(
            "INSERT INTO places (id, name, aliases, kind, modern, precision, chgis_id, geo_note, geom) VALUES "
            f"({q(pl.id)}, {q(pl.name)}, {q(pl.aliases)}::jsonb, {q(pl.kind)}, {q(pl.modern)}, "
            f"{q(pl.precision)}, {q(pl.chgis_id)}, {q(pl.geo_note)}, ST_SetSRID(ST_MakePoint({pl.lon}, {pl.lat}), 4326));")
    for k in kingdoms:
        lines.append(f"INSERT INTO kingdoms_206 (kingdom, king, capital_id) VALUES "
                     f"({q(k['kingdom'])}, {q(k['king'])}, {q(k['capital'])});")
    for p in passages:
        lines.append(
            "INSERT INTO passages (id, work, juan, year_bce, year_label, ganzhi, entry_no, kind, date_source, months, text) VALUES "
            f"({q(p.id)}, {q(p.work)}, {p.juan}, {p.year_bce}, {q(p.year_label)}, {q(p.ganzhi)}, "
            f"{p.entry_no}, {q(p.kind)}, {q(p.date_source)}, {q(p.months)}::jsonb, {q(p.text)});")
        for pid, n in p.places.items():
            lines.append(f"INSERT INTO passage_places (passage_id, place_id, mentions) VALUES "
                         f"({q(p.id)}, {q(pid)}, {n});")
    for ev in events:
        lines.append(
            "INSERT INTO events (id, title, year_bce, month, sort_key, place_id, summary) VALUES "
            f"({q(ev['id'])}, {q(ev['title'])}, {ev['year_bce']}, {ev['month']}, {ev['sort_key']}, "
            f"{q(ev['place_id'])}, {q(ev['summary'])});")
        for c in ev["citations"]:
            lines.append(f"INSERT INTO event_citations (event_id, passage_id, snippet) VALUES "
                         f"({q(ev['id'])}, {q(c['passage_id'])}, {q(c['snippet'])});")
    for e in ledger["entries"]:
        lines.append(
            "INSERT INTO ledger_entries (id, seq, year_bce, month, sort_key, place_id, event_id, title, text, goods) VALUES "
            f"({q(e['id'])}, {e['seq']}, {e['year_bce']}, {e['month']}, {e['sort_key']}, {q(e['place_id'])}, "
            f"{q(e['event_id'])}, {q(e['title'])}, {q(e['text'])}, {q(e['goods'])}::jsonb);")
    for d in divergences:
        lines.append(
            "INSERT INTO yanyi_divergences (id, type, title, passage_id, event_id, yanyi, history, sources, author_note) VALUES "
            f"({q(d['id'])}, {q(d['type'])}, {q(d['title'])}, {q(d['passage_id'])}, {q(d.get('event_id'))}, "
            f"{q(d['yanyi'])}, {q(d['history'])}, {q(d['sources'])}::jsonb, {q(d.get('author_note'))});")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def validate(gaz, events, ledger) -> list[str]:
    errors = []
    ev_ids = {e["id"] for e in events}
    for ev in events:
        if ev["place_id"] not in gaz.places:
            errors.append(f"event {ev['id']}: unknown place {ev['place_id']}")
        if not any(c["work"] == "資治通鑑" for c in ev["citations"]):
            errors.append(f"event {ev['id']}: no 資治通鑑 citation for keywords {ev['keywords']}")
    prev = None
    for e in sorted(ledger["entries"], key=lambda x: x["seq"]):
        if e["place_id"] not in gaz.places:
            errors.append(f"ledger {e['id']}: unknown place {e['place_id']}")
        if e["event_id"] and e["event_id"] not in ev_ids:
            errors.append(f"ledger {e['id']}: unknown event {e['event_id']}")
        if prev is not None and e["sort_key"] < prev:
            errors.append(f"ledger {e['id']}: out of chronological order")
        prev = e["sort_key"]
    return errors


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-web", action="store_true", help="do not copy outputs into web/public/data")
    args = ap.parse_args(argv)

    gaz = Gazetteer.from_json(json.loads((CURATED / "gazetteer.json").read_text()))
    apply_chgis(gaz, json.loads((CURATED / "chgis_v6.json").read_text()))
    kingdoms = json.loads((CURATED / "kingdoms_206.json").read_text())
    events = json.loads((CURATED / "events.json").read_text())
    ledger = json.loads((CURATED / "luqian_ledger.json").read_text())
    for e in ledger["entries"]:
        e["sort_key"] = sort_key(e["year_bce"], e["month"])

    passages = load_passages(gaz)
    for ev in events:
        ev["sort_key"] = sort_key(ev["year_bce"], ev["month"])
    date_carried(events, passages)
    link_events(events, passages)
    flag_contradictions(passages)
    for p in passages:
        if p.date_flag:
            print(f"WARN {p.id} dated {p.year_bce} ({p.date_source}): {p.date_flag}", file=sys.stderr)
    divergences, errors = resolve_divergences(
        json.loads((CURATED / "yanyi_divergences.json").read_text()), passages, events)
    passages = [p for p in passages if in_slice(p)]
    errors += validate(gaz, events, ledger)
    for err in errors:
        print("ERROR", err, file=sys.stderr)
    if errors:
        return 1

    events.sort(key=lambda e: e["sort_key"])
    dump(OUT / "passages.json", [p.to_dict() for p in passages])
    dump(OUT / "events.json", events)
    dump(OUT / "places.geojson", places_geojson(gaz, passages, kingdoms))
    dump(OUT / "luqian_route.geojson", route_geojson(gaz, ledger))
    dump(OUT / "luqian_ledger.json", ledger)
    dump(OUT / "yanyi_divergences.json", divergences)
    SEED.write_text(seed_sql(gaz, passages, events, ledger, kingdoms, divergences))
    if not args.no_web:
        WEB.mkdir(parents=True, exist_ok=True)
        for f in OUT.iterdir():
            shutil.copy(f, WEB / f.name)

    for work in ("史記", yanyi.WORK):
        ps = [p for p in passages if p.work == work]
        print(f"{work}: {len(ps)} passages, carried {sum(p.date_source == 'carried' for p in ps)}, "
              f"re-dated by event keyword {sum(p.date_source == 'event_keyword' for p in ps)}, "
              f"flagged {sum(bool(p.date_flag) for p in ps)}")
    print(f"資治通鑑: {sum(p.work == '資治通鑑' for p in passages)} passages")
    print(f"events: {len(events)}, citations: {sum(len(e['citations']) for e in events)}")
    print(f"places mentioned: {sum(1 for p in places_geojson(gaz, passages, kingdoms)['features'] if p['properties']['mentions_total'])}/{len(gaz.places)}")
    print(f"ledger entries: {len(ledger['entries'])}")
    print(f"前漢演義 divergences: {len(divergences)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
