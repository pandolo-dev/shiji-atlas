"""Build JSON/GeoJSON + PostGIS seed for the Chu–Han slice (209–202 BCE)."""
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import shiji, tongjian
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


def load_passages(gaz: Gazetteer) -> list:
    passages = []
    for juan in TONGJIAN:
        passages += tongjian.parse((RAW / f"資治通鑑_卷{juan:03d}.wiki").read_text(), juan)
    for juan, title in SHIJI.items():
        passages += shiji.parse((RAW / f"史記_卷{juan:03d}.wiki").read_text(), juan, title)
    for p in passages:
        p.places = gaz.count(p.text)
    return passages


def in_slice(p) -> bool:
    return YEAR_MIN <= p.year_bce <= YEAR_MAX


def snippet(text: str, kw: str, before: int = 30, after: int = 70) -> str:
    i = text.find(kw)
    s, e = max(0, i - before), min(len(text), i + len(kw) + after)
    return ("…" if s else "") + text[s:e].replace("\n", "") + ("…" if e < len(text) else "")


def link_events(events: list[dict], passages: list) -> None:
    for ev in events:
        cites = []
        for p in passages:
            if p.kind != "narrative":
                continue
            # 史記 paragraphs without their own year marker carry the previous
            # marker's year, which drifts; match those on keywords alone.
            if p.date_source == "carried":
                slack = None
            else:
                slack = 0 if p.work == "資治通鑑" else 1
            if slack is not None and abs(p.year_bce - ev["year_bce"]) > slack:
                continue
            if all(k in p.text for k in ev["keywords"]):
                cites.append({"passage_id": p.id, "work": p.work, "juan": p.juan,
                              "year_label": p.year_label, "snippet": snippet(p.text, ev["keywords"][0])})
        ev["citations"] = cites
        ev["sort_key"] = sort_key(ev["year_bce"], ev["month"])


def anchor_carried(events: list[dict], passages: list) -> None:
    """Re-date carried 史記 paragraphs by the (earliest) event they cite."""
    by_passage: dict[str, dict] = {}
    for ev in sorted(events, key=lambda e: sort_key(e["year_bce"], e["month"])):
        for c in ev["citations"]:
            by_passage.setdefault(c["passage_id"], ev)
    for p in passages:
        ev = by_passage.get(p.id)
        if p.date_source == "carried" and ev:
            p.year_bce = ev["year_bce"]
            p.date_source = "event"
    # Carry forward again from the nearest dated paragraph in the same chapter.
    last: dict[int, int] = {}
    for p in passages:
        if p.work != "史記":
            continue
        if p.date_source == "carried" and p.juan in last:
            p.year_bce = min(p.year_bce, last[p.juan])
        else:
            last[p.juan] = p.year_bce
    for ev in events:
        for c in ev["citations"]:
            c["year_bce"] = next(p.year_bce for p in passages if p.id == c["passage_id"])


def point(place, props: dict) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [place.lon, place.lat]},
            "properties": props}


def places_geojson(gaz: Gazetteer, passages: list, kingdoms: list[dict]) -> dict:
    by_year: dict[str, dict[int, int]] = {}
    for p in passages:
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
            "precision": pl.precision, "chgis_id": pl.chgis_id,
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


def seed_sql(gaz, passages, events, ledger, kingdoms) -> str:
    lines = ["-- Generated by `python -m shiji_atlas.build`. Do not edit by hand.", "BEGIN;"]
    for pl in gaz.places.values():
        lines.append(
            "INSERT INTO places (id, name, aliases, kind, modern, precision, chgis_id, geom) VALUES "
            f"({q(pl.id)}, {q(pl.name)}, {q(pl.aliases)}::jsonb, {q(pl.kind)}, {q(pl.modern)}, "
            f"{q(pl.precision)}, {q(pl.chgis_id)}, ST_SetSRID(ST_MakePoint({pl.lon}, {pl.lat}), 4326));")
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
    kingdoms = json.loads((CURATED / "kingdoms_206.json").read_text())
    events = json.loads((CURATED / "events.json").read_text())
    ledger = json.loads((CURATED / "luqian_ledger.json").read_text())
    for e in ledger["entries"]:
        e["sort_key"] = sort_key(e["year_bce"], e["month"])

    passages = load_passages(gaz)
    link_events(events, passages)
    anchor_carried(events, passages)
    passages = [p for p in passages if in_slice(p)]
    errors = validate(gaz, events, ledger)
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
    SEED.write_text(seed_sql(gaz, passages, events, ledger, kingdoms))
    if not args.no_web:
        WEB.mkdir(parents=True, exist_ok=True)
        for f in OUT.iterdir():
            shutil.copy(f, WEB / f.name)

    tj = sum(p.work == "資治通鑑" for p in passages)
    carried = sum(p.date_source == "carried" for p in passages)
    print(f"史記 paragraphs dated only by carry-forward: {carried}")
    print(f"passages: {len(passages)} (資治通鑑 {tj}, 史記 {len(passages) - tj})")
    print(f"events: {len(events)}, citations: {sum(len(e['citations']) for e in events)}")
    print(f"places mentioned: {sum(1 for p in places_geojson(gaz, passages, kingdoms)['features'] if p['properties']['mentions_total'])}/{len(gaz.places)}")
    print(f"ledger entries: {len(ledger['entries'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
