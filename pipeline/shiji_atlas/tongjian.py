"""Parse 資治通鑑 wikitext into year-headed, numbered entries."""
import re
from dataclasses import dataclass, field, asdict

from .numerals import cn_to_int, find_months
from .wikitext import clean_inline, preprocess

YEAR_HEADING = re.compile(
    r"^===\s*(?P<label>[^（=]+?)（(?P<ganzhi>[^，,]+)[，,](?:西元|公元)?前(?P<bce>[〇○零一二三四五六七八九十百]+)年）\s*===\s*$"
)
ENTRY_START = re.compile(r"^'''(?P<n>\d+)'''\s*(?P<rest>.*)$")


@dataclass
class Passage:
    id: str
    work: str
    juan: int
    year_bce: int
    year_label: str
    entry_no: int
    kind: str  # "narrative" | "commentary"
    text: str
    ganzhi: str = ""
    months: list[int] = field(default_factory=list)
    places: dict[str, int] = field(default_factory=dict)
    date_source: str = "heading"  # heading | marker | carried | event

    def to_dict(self) -> dict:
        return asdict(self)


def parse(raw: str, juan: int) -> list[Passage]:
    text = preprocess(raw)
    out: list[Passage] = []
    year = None
    entry_no = 0
    narrative: list[str] = []
    commentary: list[str] = []

    def flush():
        nonlocal narrative, commentary
        if year and entry_no:
            label, ganzhi, bce = year
            base = f"tj-{juan:03d}-{bce}-{entry_no:02d}"
            if narrative:
                body = "\n".join(narrative)
                out.append(Passage(base, "資治通鑑", juan, bce, label, entry_no, "narrative",
                                   body, ganzhi, find_months(body)))
            if commentary:
                body = "\n".join(commentary)
                out.append(Passage(base + "c", "資治通鑑", juan, bce, label, entry_no, "commentary",
                                   body, ganzhi, []))
        narrative, commentary = [], []

    for line in text.splitlines():
        line = line.rstrip()
        m = YEAR_HEADING.match(line)
        if m:
            flush()
            year = (m.group("label").strip(), m.group("ganzhi").strip(), cn_to_int(m.group("bce")))
            entry_no = 0
            continue
        if line.startswith("==") or line.startswith("----"):
            if line.startswith("=="):
                flush()
                entry_no = 0
            continue
        m = ENTRY_START.match(line)
        if m and year:
            flush()
            entry_no = int(m.group("n"))
            line = m.group("rest")
        if not entry_no or not line.strip():
            continue
        if line.startswith(":"):
            cleaned = clean_inline(line.lstrip(":"))
            if cleaned:
                commentary.append(cleaned)
        else:
            cleaned = clean_inline(line)
            if cleaned:
                narrative.append(cleaned)
    flush()
    return out
