import json
import unittest
from pathlib import Path

from shiji_atlas import build, shiji, tongjian, yanyi
from shiji_atlas.gazetteer import Gazetteer, Place
from shiji_atlas.numerals import cn_to_int, find_months, sort_key
from shiji_atlas.wikitext import clean_inline, preprocess

ROOT = Path(__file__).resolve().parents[2]


class NumeralTests(unittest.TestCase):
    def test_cn_to_int(self):
        self.assertEqual(cn_to_int("二〇八"), 208)
        self.assertEqual(cn_to_int("二十三"), 23)
        self.assertEqual(cn_to_int("十二"), 12)
        self.assertEqual(cn_to_int("元"), 1)

    def test_months_and_sort_key_follow_zhuanxu_year(self):
        self.assertEqual(find_months("冬，十月，沛公至霸上。十一月"), [10, 11])
        self.assertEqual(find_months("正月"), [1])
        # 十月 opens the civil year, so 高帝元年十月 precedes 高帝元年二月.
        self.assertLess(sort_key(206, 10), sort_key(206, 2))
        self.assertLess(sort_key(206, 9), sort_key(205, 10))


class WikitextTests(unittest.TestCase):
    def test_clean_inline(self):
        raw = "[[w:陽城|陽城]]人也，若為-{zh-hans:佣; zh-hant:庸;}-耕，守{{另|熒|滎}}陽'''1'''"
        self.assertEqual(clean_inline(raw), "陽城人也，若為庸耕，守滎陽1")

    def test_preprocess_drops_multiline_refs(self):
        self.assertEqual(preprocess("蒙恬<ref>梁玉繩\n曰</ref>將"), "蒙恬將")


class GazetteerTests(unittest.TestCase):
    def setUp(self):
        self.gaz = Gazetteer([
            Place("chen", "陳", 0, 0, exclude_next="勝涉王"),
            Place("chenliu", "陳留", 0, 0),
            Place("pei", "沛", 0, 0, exclude_next="公令"),
        ])

    def test_single_char_needs_locative_prefix(self):
        self.assertEqual(self.gaz.count("陳勝至陳而王"), {"chen": 1})
        self.assertEqual(self.gaz.count("沛公還軍"), {})
        self.assertEqual(self.gaz.count("起兵於沛"), {"pei": 1})

    def test_longest_alias_wins(self):
        self.assertEqual(self.gaz.count("攻陳留"), {"chenliu": 1})


class ParserTests(unittest.TestCase):
    def test_tongjian_heading_and_entries(self):
        raw = (ROOT / "data/raw/資治通鑑_卷009.wiki").read_text()
        ps = tongjian.parse(raw, 9)
        first = ps[0]
        self.assertEqual((first.year_bce, first.year_label, first.ganzhi, first.entry_no), (206, "高帝元年", "乙未", 1))
        self.assertIn("沛公至霸上", first.text)
        self.assertTrue(any(p.kind == "commentary" and "賈誼" in p.text for p in ps))

    def test_shiji_inline_year_markers(self):
        raw = (ROOT / "data/raw/史記_卷008.wiki").read_text()
        ps = {p.text[:7]: p for p in shiji.parse(raw, 8, "高祖本紀")}
        self.assertEqual(ps["漢元年十月，沛"].year_bce, 206)
        self.assertEqual(ps["五年，高祖與諸"].year_bce, 202)
        self.assertEqual(ps["五年，高祖與諸"].date_source, "marker")

    def test_shiji_splits_paragraph_on_later_marker(self):
        raw = "秦二世元年秋，陳勝等起蘄，至陳而王。其後漢元年十月，沛公兵遂先諸侯至霸上。"
        ps = shiji.parse(raw, 8, "高祖本紀")
        self.assertEqual([(p.id, p.year_bce, p.date_source) for p in ps],
                         [("sj-008-001a", 209, "marker"), ("sj-008-001b", 206, "marker")])
        self.assertTrue(ps[1].text.startswith("漢元年"))

    def test_shiji_commentary_runs_to_chapter_end(self):
        raw = "秦二世元年秋，陳勝起。\n太史公曰：吾聞之周生曰。\n二世三年，其後論贊之文如此。"
        ps = shiji.parse(raw, 8, "高祖本紀")
        self.assertEqual([p.kind for p in ps], ["narrative", "commentary", "commentary"])


class YanyiTests(unittest.TestCase):
    CH9 = ("{{header\n| title = 前漢演義\n}}\n\n\u3000\u3000卻說二世再興土木。\n\n"
           "\u3000\u3000到了二世元年七月，陳勝吳廣起事。\n\n\u3000\u3000飾禮寧知真下士？偽恭但欲暫欺人。\n\n"
           "\u3000\u3000畢竟大梁二士姓甚名誰，容待下回詳報。\n\n\n\u3000\u3000暴秦之季，發難者為陳勝吳廣。")
    CH10 = "\u3000\u3000陳勝稱王。時已為漢王二年了，彭城大敗。\n\u3000\u3000欲知後事，且看下回。\n\u3000\u3000本回評語。"

    def test_kinds_and_year_carried_across_chapters(self):
        ps = yanyi.parse([(9, self.CH9), (10, self.CH10)])
        self.assertEqual([(p.id, p.kind, p.year_bce, p.date_source) for p in ps], [
            ("yy-009-001", "narrative", 209, "carried"),
            ("yy-009-002", "narrative", 209, "marker"),
            ("yy-009-003", "aside", 209, "carried"),
            ("yy-009-004", "aside", 209, "carried"),
            ("yy-009-005", "commentary", 209, "carried"),
            ("yy-010-001a", "narrative", 209, "carried"),
            ("yy-010-001b", "narrative", 205, "marker"),
            ("yy-010-002", "aside", 205, "carried"),
            ("yy-010-003", "commentary", 205, "carried"),
        ])

    def test_yanyi_keywords_and_rejected_anchor_not_cited(self):
        p = tongjian.Passage("yy-030-001", yanyi.WORK, 30, 204, "x", 1, "narrative",
                             "從前鴻門會宴時，臣曾勸大王。劃鴻溝為界", date_flag="anchor_rejected(hongmen)")
        evs = [ev("hongmen", 205, "鴻門"), ev("honggou", 203, "洪溝", yanyi_keywords=["鴻溝"])]
        build.link_events(evs, [p])
        self.assertEqual([len(e["citations"]) for e in evs], [0, 1])

    def test_divergence_quotes_resolve_or_fail(self):
        ps = [tongjian.Passage("yy-031-001", yanyi.WORK, 31, 202, "x", 1, "narrative", "張子房編出一曲楚歌"),
              sj(40, 202, "夜聞漢軍四面皆楚歌")]
        item = {"id": "chuge", "type": "embellished", "chapter": 31, "anchor": "編出一曲楚歌", "sources": [
            {"work": "史記", "juan": 7, "title": "項羽本紀", "quote": "四面皆楚歌"},
            {"work": "史記", "juan": 55, "title": "留侯世家", "quote": "不在語料"}]}
        doc = {"types": {"embellished": "增飾"}, "items": [item]}
        out, errors = build.resolve_divergences(doc, ps, [])
        self.assertEqual((errors, out[0]["passage_id"]), ([], "yy-031-001"))
        self.assertEqual([s["passage_id"] for s in out[0]["sources"]], ["sj-007-040", None])
        bad = dict(item, sources=[{"work": "史記", "juan": 7, "title": "項羽本紀", "quote": "無此語"}])
        self.assertEqual(len(build.resolve_divergences({**doc, "items": [bad]}, ps, [])[1]), 1)


def sj(i, year, text, source="carried"):
    return tongjian.Passage(f"sj-007-{i:03d}", "史記", 7, year, "項羽本紀·x", i, "narrative", text,
                            date_source=source)


def ev(eid, year, kw, **extra):
    return {"id": eid, "title": eid, "year_bce": year, "month": 1, "keywords": [kw],
            "sort_key": sort_key(year, 1), **extra}


class DatingTests(unittest.TestCase):
    def test_carried_keyword_outside_window_is_not_anchored(self):
        ps = [sj(1, 208, "二世二年", "marker"), sj(2, 208, "項王數之曰：坑秦卒於新安"), sj(3, 208, "後事")]
        build.date_carried([ev("xinan", 206, "新安")], ps)
        self.assertEqual([(p.year_bce, p.date_source) for p in ps[1:]], [(208, "carried"), (208, "carried")])

    def test_window_chains_in_document_order(self):
        ps = [sj(1, 208, "二世二年", "marker"), sj(2, 208, "鉅鹿之戰"), sj(3, 208, "到新安"), sj(4, 208, "後事")]
        build.date_carried([ev("julu", 207, "鉅鹿"), ev("xinan", 206, "新安")], ps)
        self.assertEqual([p.year_bce for p in ps], [208, 207, 206, 206])
        self.assertEqual(ps[2].date_source, "event_keyword")

    def test_anchor_outside_neighbour_markers_is_rejected(self):
        ps = [sj(1, 204, "三年", "marker"), sj(2, 204, "彭越渡睢水"), sj(3, 203, "四年", "marker")]
        build.date_carried([ev("pengcheng", 205, "睢水")], ps)
        self.assertEqual((ps[1].year_bce, ps[1].date_flag), (204, "anchor_rejected(pengcheng)"))

    def test_allowlist_overrides_window(self):
        ps = [sj(1, 208, "二世二年", "marker"), sj(2, 208, "無關鍵字")]
        build.date_carried([ev("xinan", 206, "新安", passages=["sj-007-002"])], ps)
        self.assertEqual((ps[1].year_bce, ps[1].date_source), (206, "event_allowlist"))

    def test_flag_contradicting_both_neighbours(self):
        ps = [sj(1, 204, "", "marker"), sj(2, 206, "", "event_allowlist"), sj(3, 203, "", "marker")]
        self.assertEqual([p.id for p in build.flag_contradictions(ps)], ["sj-007-002"])


class BuildTests(unittest.TestCase):
    def test_build_outputs_validate(self):
        self.assertEqual(build.main(["--no-web"]), 0)
        events = json.loads((ROOT / "data/out/events.json").read_text())
        honggou = next(e for e in events if e["id"] == "honggou")
        self.assertTrue(any("洪溝" in c["snippet"] for c in honggou["citations"]))
        route = json.loads((ROOT / "data/out/luqian_route.geojson").read_text())
        self.assertEqual(route["features"][0]["geometry"]["type"], "LineString")

    def test_chgis_matches_are_near_curated_site(self):
        from shiji_atlas import chgis
        places = [{"id": "guangwu", "name": "廣武", "lon": 113.5, "lat": 34.9},
                  {"id": "xingyang", "name": "滎陽", "lon": 113.4, "lat": 34.8},
                  {"id": "feng", "name": "豐", "lon": 116.6, "lat": 34.7}]
        rec = lambda sid, n, lon, lat, y0, y1: {"SYS_ID": sid, "NAME_FT": n, "TYPE_CH": "縣", "X_COOR": lon,  # noqa: E731
                                                "Y_COOR": lat, "BEG_YR": y0, "END_YR": y1, "PRES_LOC": ""}
        recs = [rec(1, "廣武縣", 112.9, 39.1, -204, 13), rec(2, "滎陽縣", 113.45, 34.82, -221, 492),
                rec(3, "滎陽縣", 116.0, 30.0, -221, 13), rec(4, "豐縣", 116.6, 34.7, -154, 13)]
        res = chgis.match(places, recs)
        self.assertEqual(res["guangwu"]["status"], "rejected")
        self.assertEqual((res["xingyang"]["status"], res["xingyang"]["sys_id"]), ("matched", 2))
        self.assertEqual(res["feng"]["status"], "no_instance")

    def test_committed_chgis_ids_are_vetted(self):
        doc = json.loads((ROOT / "data/curated/chgis_v6.json").read_text())
        for pid, m in doc["places"].items():
            if m["status"] in ("matched", "adjacent"):
                self.assertLessEqual(m["offset_km"], 50, pid)
        self.assertNotIn("lon", doc["places"]["guangwu"])


if __name__ == "__main__":
    unittest.main()
