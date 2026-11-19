"""Parse 史記 chapter wikitext into dated paragraphs.

史記 has no year headings; dates are inline (秦二世元年七月, 漢之二年 …), so the
current year is carried forward from the latest marker seen.
"""
import re

from .numerals import cn_to_int, find_months
from .tongjian import Passage
from .wikitext import clean_inline, preprocess

QIN_YEAR = re.compile(r"(?:秦)?二世(元|二|三)年")
HAN_YEAR = re.compile(r"漢(?:之)?(元|二|三|四|五|六|七|八|九|十|十一|十二)年")
BARE_YEAR = re.compile(r"(?:^|[。」：])(二|三|四|五|六|七|八|九|十|十一|十二)年")


def year_markers(text: str, era: str | None) -> list[tuple[int, int, str]]:
    """Return (offset, year_bce, era) markers found in text, in order."""
    found = []
    for m in QIN_YEAR.finditer(text):
        found.append((m.start(), 210 - cn_to_int(m.group(1)), "qin"))
    for m in HAN_YEAR.finditer(text):
        found.append((m.start(), 207 - cn_to_int(m.group(1)), "han"))
    found.sort()
    if era == "han" or any(e == "han" for _, _, e in found):
        han_start = next((o for o, _, e in found if e == "han"), 0) if era != "han" else 0
        for m in BARE_YEAR.finditer(text):
            if m.start(1) >= han_start and not any(abs(m.start(1) - o) < 4 for o, _, _ in found):
                found.append((m.start(1), 207 - cn_to_int(m.group(1)), "han"))
        found.sort()
    return found


# 太史公曰/褚先生曰 always open the chapter tail (論贊, 索隱述贊, 過秦論), so once
# seen every later paragraph is commentary.
COMMENTARY_START = re.compile(r"^(太史公曰|褚先生曰)")
MIN_SEGMENT = 8  # a marker this close to the start dates the whole segment instead of splitting


def segments(text: str, markers: list[tuple[int, int, str]]) -> list[tuple[str, list]]:
    """Split text before each marker so every segment starts with at most one regnal year."""
    cuts = [0]
    for o, _, _ in markers:
        if o - cuts[-1] >= MIN_SEGMENT and len(text) - o >= MIN_SEGMENT:
            cuts.append(o)
    cuts.append(len(text))
    out = []
    for a, b in zip(cuts, cuts[1:]):
        own = [m for m in markers if a <= m[0] < b]
        out.append((text[a:b], [(o - a, y, e) for o, y, e in own]))
    return out


def parse(raw: str, juan: int, title: str) -> list[Passage]:
    """Each passage gets date_source "marker" (opens with its own year marker) or "carried"."""
    text = preprocess(raw)
    out: list[Passage] = []
    year, era, label = None, None, ""
    para = 0
    in_commentary = False
    for line in text.splitlines():
        if not line.strip() or line.startswith(("=", "{", "|", "}", "[[Category")):
            continue
        cleaned = clean_inline(line)
        if len(cleaned) < 8:
            continue
        para += 1
        if COMMENTARY_START.match(cleaned):
            in_commentary = True
        markers = [] if in_commentary else year_markers(cleaned, era)
        segs = segments(cleaned, markers)
        for k, (seg, own) in enumerate(segs):
            dated = bool(own) and own[0][0] < MIN_SEGMENT
            if dated:
                year, era = own[0][1], own[0][2]
                label = seg[own[0][0]:own[0][0] + 8]
            if year is not None:
                pid = f"sj-{juan:03d}-{para:03d}" + ("abcdefghij"[k] if len(segs) > 1 else "")
                out.append(Passage(pid, "史記", juan, year, f"{title}·{label}", para,
                                   "commentary" if in_commentary else "narrative", seg, "",
                                   find_months(seg), date_source="marker" if dated else "carried"))
            if own:
                year, era = own[-1][1], own[-1][2]
    return out
