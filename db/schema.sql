-- Chu–Han slice (209–202 BCE). Loaded automatically by docker-compose (00-schema.sql).
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE places (
    id         text PRIMARY KEY,
    name       text NOT NULL,
    aliases    jsonb NOT NULL DEFAULT '[]',
    kind       text NOT NULL,
    modern     text,
    precision  text NOT NULL DEFAULT 'approx',  -- approx | chgis | chgis_adjacent
    chgis_id   text,                            -- CHGIS V6 TGAZ id (hvd_<SYS_ID>)
    geo_note   text,                            -- CHGIS instance, or why there is none
    geom       geometry(Point, 4326) NOT NULL
);
CREATE INDEX places_geom_idx ON places USING gist (geom);

CREATE TABLE kingdoms_206 (
    kingdom    text PRIMARY KEY,
    king       text NOT NULL,
    capital_id text NOT NULL REFERENCES places(id)
);

CREATE TABLE passages (
    id          text PRIMARY KEY,
    work        text NOT NULL,       -- 資治通鑑 | 史記
    juan        int  NOT NULL,
    year_bce    int  NOT NULL,       -- Tongjian year label, e.g. 206 for 高帝元年
    year_label  text NOT NULL,
    ganzhi      text,
    entry_no    int  NOT NULL,
    kind        text NOT NULL,       -- narrative | commentary
    date_source text NOT NULL,       -- heading | marker | event | carried
    months      jsonb NOT NULL DEFAULT '[]',
    text        text NOT NULL
);
CREATE INDEX passages_year_idx ON passages (year_bce);

CREATE TABLE passage_places (
    passage_id text NOT NULL REFERENCES passages(id) ON DELETE CASCADE,
    place_id   text NOT NULL REFERENCES places(id),
    mentions   int  NOT NULL,
    PRIMARY KEY (passage_id, place_id)
);

CREATE TABLE events (
    id        text PRIMARY KEY,
    title     text NOT NULL,
    year_bce  int  NOT NULL,
    month     int,
    sort_key  double precision NOT NULL,
    place_id  text NOT NULL REFERENCES places(id),
    summary   text
);

CREATE TABLE event_citations (
    event_id   text NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    passage_id text NOT NULL REFERENCES passages(id),
    snippet    text NOT NULL,
    PRIMARY KEY (event_id, passage_id)
);

-- Fictional ledger of the itinerant merchant 陸遷.
CREATE TABLE ledger_entries (
    id        text PRIMARY KEY,
    seq       int  NOT NULL UNIQUE,
    year_bce  int  NOT NULL,
    month     int,
    sort_key  double precision NOT NULL,
    place_id  text NOT NULL REFERENCES places(id),
    event_id  text REFERENCES events(id),
    title     text NOT NULL,
    text      text NOT NULL,
    goods     jsonb NOT NULL DEFAULT '[]'
);

CREATE VIEW luqian_route AS
SELECT ST_MakeLine(p.geom ORDER BY l.seq) AS geom,
       count(*)                           AS stops,
       ST_Length(ST_MakeLine(p.geom ORDER BY l.seq)::geography) / 1000 AS length_km
FROM ledger_entries l JOIN places p ON p.id = l.place_id;
