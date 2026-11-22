"""Parse 蔡東藩《前漢演義》chapters (回) into dated paragraphs.

The novel is vernacular and continuous across chapters, so the running year is
carried from chapter to chapter. Year markers are sparse (二世元年, 漢王二年 …).
Each chapter ends with a closing formula (下回分解), then 蔡東藩's own 評; inline 夾批 (e.g. 特標年月，點清眉目。) are not marked in the
source and stay in the narrative text.
"""
import re

from .numerals import cn_to_int, find_months
from .shiji import MIN_SEGMENT, QIN_YEAR, segments
from .tongjian import Passage
from .wikitext import clean_inline, preprocess

WORK = "前漢演義"
HAN_YEAR = re.compile(r"漢(?:王)?(元|二|三|四|五)年")
CLAUSE = re.compile(r"([^，。！？「」]+)[，。！？]")
CLOSING = re.compile(r"下回|下文")
START = (209, "秦二世元年")  # 第九回 opens in 二世元年


def year_markers(text: str) -> list[tuple[int, int, str]]:
    found = [(m.start(), 210 - cn_to_int(m.group(1)), "qin") for m in QIN_YEAR.finditer(text)]
    found += [(m.start(), 207 - cn_to_int(m.group(1)), "han") for m in HAN_YEAR.finditer(text)]
    return sorted(found)


def is_verse(text: str) -> bool:
    """A couplet line: 2 or 4 clauses, all of 5 or all of 7 characters."""
    clauses = CLAUSE.findall(text)
    return ("".join(c + "x" for c in clauses) == re.sub(r"[，。！？]", "x", text)
            and len(clauses) in (2, 4) and len({len(c) for c in clauses}) == 1 and len(clauses[0]) in (5, 7))


def paragraphs(raw: str) -> list[tuple[str, bool]]:
    """Return (cleaned paragraph, is_tail_commentary); the 評 follows the closing formula."""
    lines = [clean_inline(line) for line in preprocess(raw).splitlines()
             if not line.startswith(("{", "|", "}", "[[Category"))]
    lines = [line for line in lines if line]
    close = max((i for i, line in enumerate(lines) if CLOSING.search(line)), default=len(lines))
    return [(line, i > close) for i, line in enumerate(lines)]


def parse(chapters: list[tuple[int, str]], start: tuple[int, str] = START) -> list[Passage]:
    """chapters: (回 number, raw wikitext) in reading order."""
    out: list[Passage] = []
    year, label = start
    for n, raw in chapters:
        paras = paragraphs(raw)
        last_story = max((i for i, (_, c) in enumerate(paras) if not c), default=-1)
        for i, (text, commentary) in enumerate(paras, 1):
            if commentary:
                kind = "commentary"
            elif (i - 1 == last_story and CLOSING.search(text) and len(text) < 40) or is_verse(text):
                kind = "aside"  # closing formula (下回分解) or couplet
            else:
                kind = "narrative"
            markers = year_markers(text) if kind == "narrative" else []
            segs = segments(text, markers)
            for k, (seg, own) in enumerate(segs):
                dated = bool(own) and own[0][0] < MIN_SEGMENT
                if dated:
                    year, label = own[0][1], seg[own[0][0]:own[0][0] + 6]
                pid = f"yy-{n:03d}-{i:03d}" + ("abcdefghij"[k] if len(segs) > 1 else "")
                out.append(Passage(pid, WORK, n, year, f"第{n}回·{label}", i, kind, seg, "",
                                   find_months(seg), date_source="marker" if dated else "carried"))
                if own:
                    year, label = own[-1][1], seg[own[-1][0]:own[-1][0] + 6]
    return out
