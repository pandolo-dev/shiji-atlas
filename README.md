# shiji-atlas

《史记》《资治通鉴》时间轴 + 历史 GIS 地图联动原型（秦末楚汉，前209–前202），跟随虚构行脚商陆迁的账本。

## Layout

| Path | What |
| --- | --- |
| `data/raw/` | 维基文库 wikitext snapshots (史記 卷7/8/48, 資治通鑑 卷7–11). See `SOURCE.md`. |
| `data/curated/` | Hand-curated inputs: `gazetteer.json` (places + approx coords), `events.json`, `kingdoms_206.json`, `luqian_ledger.json` (fictional). |
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
   - `marker`: has its own year marker
   - `event`: re-dated from the curated event it cites
   - `carried`: inherits the previous paragraph's year (least reliable)

   `太史公曰` / `褚先生曰` and everything after them is marked as `commentary`.
4. **Places** (`gazetteer.py`): longest-alias-first matching. One-character names (陳, 沛, 豐, 薛, 宛) only count when preceded by a locative verb/preposition (至陳, 攻豐…) and not followed by an excluded char (陳勝, 沛公).
5. **Events** (`build.py`): each curated event has keywords. It is linked to every passage in the same year that contains all of them. Missing 資治通鑑 citations fail the build.

## Caveats

- **Coordinates are approximate** (modern-site estimates, `precision: "approx"`, `chgis_id: null`). Next step: replace them with CHGIS v6 points.
- **Calendar**: Qin and early Han years begin in 十月. `year_bce` follows 資治通鑑's label, so 高帝元年十月 is stored as 206 even though it falls in late 207 BCE. The `sort_key` orders months 十月 → 九月.
- **陆迁 and his ledger are fictional.** The events, dates and places they link to come from the sources.
- Basemap tiles: OpenStreetMap (prototype use only; switch to a self-hosted or keyed provider before any public deploy).
