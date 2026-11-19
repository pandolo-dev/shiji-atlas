"""Match the curated gazetteer against CHGIS V6 time-series points.

Inputs: the .dbf files of `v6_time_cnty_pts_utf_wgs84` and `v6_time_pref_pts_utf_wgs84`
(Harvard Dataverse doi:10.7910/DVN/Q9VOF5, doi:10.7910/DVN/WW1PD6). CHGIS is not
redistributable, so the files are not committed; only the matched points are, in
data/curated/chgis_v6.json, which build.py applies on top of gazetteer.json.

    python -m shiji_atlas.chgis --cnty .../v6_time_cnty_pts_utf_wgs84.dbf --pref .../v6_time_pref_pts_utf_wgs84.dbf
"""
import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAZ = ROOT / "data" / "curated" / "gazetteer.json"
OUT = ROOT / "data" / "curated" / "chgis_v6.json"

YEAR_FROM, YEAR_TO = -209, -202
SUFFIX = re.compile(r"(侯國|國|縣|郡|道|邑)$")
MAX_KM = 50  # a same-name instance farther than this from the curated site is a different place

# Same-name instance in the slice, but a different place.
REJECT = {"guangwu": "V6 本時段的廣武縣在今山西代縣，非滎陽北之廣武；河南廣武最早實例為 584 年"}
# Seat instance starts just after the slice; the seat itself predates it.
ADJACENT = {"yuyang": "漁陽郡治實例始於前201年，晚於切片末年一年；秦已置漁陽郡，採用其點"}
# Not administrative seats, so outside the scope of the V6 point layers.
NON_ADMIN = {"dazexiang", "aocang", "honggou", "hangu", "wuguan", "bashang", "hongmen",
             "gaixia", "lingbi", "guling", "wujiang"}


def read_dbf(path: Path) -> list[dict]:
    data = path.read_bytes()
    n, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields, off = [], 32
    while data[off] != 0x0D:
        name = data[off:off + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, chr(data[off + 11]), data[off + 16]))
        off += 32
    rows = []
    for i in range(n):
        rec, pos, row = data[hlen + i * rlen: hlen + (i + 1) * rlen], 1, {}
        if rec[:1] == b"*":
            continue
        for name, typ, size in fields:
            raw = rec[pos:pos + size].decode("utf-8", "replace").strip()
            pos += size
            if typ in "NF":
                ok = raw and not raw.startswith("*")
                row[name] = (float(raw) if "." in raw else int(raw)) if ok else None
            else:
                row[name] = raw
        rows.append(row)
    return rows


def km(lon1, lat1, lon2, lat2) -> float:
    r = math.pi / 180
    x = (lon2 - lon1) * r * math.cos((lat1 + lat2) / 2 * r)
    return 6371 * math.hypot(x, (lat2 - lat1) * r)


def overlaps(r: dict) -> bool:
    return r["BEG_YR"] <= YEAR_TO and r["END_YR"] >= YEAR_FROM


def match(places: list[dict], recs: list[dict]) -> dict:
    out = {}
    for p in places:
        names = {p["name"], *p.get("aliases", [])}
        cands = [r for r in recs if SUFFIX.sub("", r["NAME_FT"]) in names or r["NAME_FT"] in names]
        dist = lambda r: km(p["lon"], p["lat"], r["X_COOR"], r["Y_COOR"])  # noqa: E731
        inr = sorted((r for r in cands if overlaps(r)), key=dist)
        best = inr[0] if inr else None
        row: dict = {"name": p["name"]}
        if p["id"] in REJECT:
            row.update(status="rejected", reason=REJECT[p["id"]])
        elif best and dist(best) <= MAX_KM:
            row.update(status="matched")
        elif p["id"] in ADJACENT:
            best = min(cands, key=lambda r: abs(r["BEG_YR"] - YEAR_TO)) if cands else None
            row.update(status="adjacent", reason=ADJACENT[p["id"]])
        elif p["id"] in NON_ADMIN:
            best = None
            row.update(status="non_admin", reason="非行政治所，V6 行政點層不覆蓋")
        else:
            first = min(cands, key=lambda r: r["BEG_YR"]) if cands else None
            reason = f"V6 本時段無實例（最早 {first['BEG_YR']}）" if first else "V6 無同名記錄"
            best = None
            row.update(status="no_instance", reason=reason)
        if best and row["status"] in ("matched", "adjacent"):
            row.update(sys_id=best["SYS_ID"], name_ft=best["NAME_FT"], type=best["TYPE_CH"],
                       years=[best["BEG_YR"], best["END_YR"]], lon=best["X_COOR"], lat=best["Y_COOR"],
                       pres_loc=best["PRES_LOC"], offset_km=round(dist(best), 1))
        elif best:
            row.update(sys_id=best["SYS_ID"], offset_km=round(dist(best), 1))
        out[p["id"]] = row
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnty", type=Path, required=True)
    ap.add_argument("--pref", type=Path, required=True)
    a = ap.parse_args(argv)
    recs = read_dbf(a.cnty) + read_dbf(a.pref)
    res = match(json.loads(GAZ.read_text()), recs)
    doc = {"source": "CHGIS, Version 6. (c) Fairbank Center for Chinese Studies of Harvard University "
                     "and the Center for Historical Geographical Studies at Fudan University, 2016.",
           "layers": ["v6_time_cnty_pts_utf_wgs84", "v6_time_pref_pts_utf_wgs84"],
           "filter": f"BEG_YR <= {YEAR_TO} AND END_YR >= {YEAR_FROM}",
           "places": res}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    counts: dict[str, int] = {}
    for r in res.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(counts, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
