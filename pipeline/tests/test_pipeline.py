import json
import unittest
from pathlib import Path

from shiji_atlas import build, shiji, tongjian
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


class BuildTests(unittest.TestCase):
    def test_build_outputs_validate(self):
        self.assertEqual(build.main(["--no-web"]), 0)
        events = json.loads((ROOT / "data/out/events.json").read_text())
        honggou = next(e for e in events if e["id"] == "honggou")
        self.assertTrue(any("洪溝" in c["snippet"] for c in honggou["citations"]))
        route = json.loads((ROOT / "data/out/luqian_route.geojson").read_text())
        self.assertEqual(route["features"][0]["geometry"]["type"], "LineString")


if __name__ == "__main__":
    unittest.main()
