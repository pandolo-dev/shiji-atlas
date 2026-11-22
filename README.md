# shiji-atlas

《史记》《资治通鉴》时间轴 + 历史 GIS 地图联动原型（秦末楚汉，前209–前202），跟随虚构行脚商陆迁的账本。

## Layout

| Path | What |
| --- | --- |
| `data/raw/` | 维基文库 wikitext snapshots (史記 卷7/8/48, 資治通鑑 卷7–11, 蔡東藩《前漢演義》第9–32回). See `SOURCE.md`. |
| `data/curated/` | Hand-curated inputs: `gazetteer.json` (places + approx coords), `chgis_v6.json` (CHGIS V6 matches, applied over the approx coords), `events.json`, `kingdoms_206.json`, `luqian_ledger.json` (fictional). |
| `pipeline/` | Python 3.10, stdlib only. Regex cleaning → parsing → place matching → event citation linking → outputs. |
| `db/` | PostGIS schema + generated `seed.sql`. |
| `web/` | React + Vite + MapLibre GL split-screen map/timeline. Reads `web/public/data/*`. |

## Run

```bash
# 1. Rebuild data (writes data/out/, web/public/data/, db/seed.sql)
cd pipeline && python -m shiji_atlas.build && python -m unittest discover -s tests -t .

# 2. PostGIS (schema + seed load on first start)
docker compose up -d
docker compose exec db psql -U shiji -d shiji_atlas -c "select stops, length_km from luqian_route;"

# 3. Web
cd web && npm install && npm run dev
```

## Pipeline

1. **Cleaning** (`wikitext.py`): strips `<ref>` notes, templates (`{{另|熒|滎}}` keeps the 2nd reading), `-{…}-` conversions, wiki links.
2. **資治通鑑** (`tongjian.py`): year headings `=== 高帝元年（乙未，公元前二〇六年） ===` → `year_bce`, `ganzhi`; numbered entries `'''N'''`; `::` lines (臣光曰, 賈誼論…) become `commentary` passages.
3. **史記** (`shiji.py`): no headings, so years come from inline markers (`秦二世元年`, `漢之二年`, bare `三年` once in the Han era). Each paragraph gets a `date_source`:
   - `marker`: opens with its own year marker. Paragraphs are split before any later marker, so ids like `sj-007-024a` and `sj-007-024b` are one source paragraph.
   - `event_keyword`: re-dated to an event whose keywords it contains. The event's year must be within ±1 of the running year and between the running year and the next marker.
   - `event_allowlist`: re-dated by an explicit `passages` list in `events.json`.
   - `carried`: inherits the immediately preceding dated paragraph's year, in strict document order (least reliable).

   A keyword match that is rejected, or a year that falls outside both marker-dated neighbours, sets `date_flag` and prints a warning during the build.

   `太史公曰` / `褚先生曰` and everything after them is marked as `commentary`.
4. **Places** (`gazetteer.py`): longest-alias-first matching. One-character names (陳, 沛, 豐, 薛, 宛) only count when preceded by a locative verb/preposition (至陳, 攻豐…) and not followed by an excluded char (陳勝, 沛公).
4b. **前漢演義** (`yanyi.py`): 蔡東藩's 1925 vernacular novel, 第9回 (大澤鄉) to 第32回 (即帝位). It is read as one continuous text, so the year carries across chapters, using the same markers, ±1 keyword window and flags as 史記 (`二世元年`, `漢王二年`). Lines after the closing formula (`下回分解`) are 蔡東藩's 評 (`commentary`); couplets and the closing formula are `aside`. His inline 夾批 (e.g. `特標年月，點清眉目。`) are not marked in the source and stay in the narrative text. The novel is cited under events but never counts toward map mentions. `data/curated/yanyi_divergences.json` lists episodes where it departs from 《史記》; the build checks every anchor and every quote that falls inside the corpus.
5. **Events** (`build.py`): each curated event has keywords. It is linked to every passage that contains all of them and is in the same year (資治通鑑) or within ±1 year (史記). Missing 資治通鑑 citations fail the build.

## Caveats

- **Coordinates**: 34 of the 55 places use CHGIS V6 time-series county/prefecture points whose instance overlaps 前209–前202 (`precision: "chgis"`, `chgis_id: hvd_<SYS_ID>`). 漁陽 uses the 前201 commandery seat (`chgis_adjacent`). The other 20 keep approximate coordinates, and `geo_note` says why: either V6 has no instance in this period (豐, 新安, 廢丘…), the place is not an administrative seat (霸上, 鴻門, 垓下…), or the match was rejected (廣武: V6's 廣武縣 is in Shanxi). To re-run the match, download the UTF-8/WGS84 point layers from [CHGIS V6](https://dataverse.harvard.edu/dataverse/chgis_v6) and run `python -m shiji_atlas.chgis --cnty <cnty .dbf> --pref <pref .dbf>`. CHGIS data is © Harvard Fairbank Center / Fudan CHGS (2016), licensed for academic, non-commercial use.
- **Calendar**: Qin and early Han years begin in 十月. `year_bce` follows 資治通鑑's label, so 高帝元年十月 is stored as 206 even though it falls in late 207 BCE. The `sort_key` orders months 十月 → 九月.
- **陆迁 and his ledger are fictional.** The events, dates and places they link to come from the sources.
- Basemap tiles: OpenStreetMap (prototype use only; switch to a self-hosted or keyed provider before any public deploy).
