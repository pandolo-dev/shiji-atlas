"""Alias matching of place names inside classical text."""
import re
from dataclasses import dataclass, field

# Characters that, when directly preceding a one-character toponym, signal
# a locative reading (至陳、攻陳、都陳、下陳 …) rather than a personal name.
LOCATIVE_PREFIX = set("至於于入攻擊屯守走還之如都下圍拔居過出渡從起反略定救距屠歸")


@dataclass
class Place:
    id: str
    name: str
    lon: float
    lat: float
    kind: str = "settlement"
    aliases: list[str] = field(default_factory=list)
    exclude_next: str = ""
    match: bool = True
    modern: str = ""
    precision: str = "approx"
    chgis_id: str | None = None
    geo_note: str = ""

    @property
    def names(self) -> list[str]:
        return [self.name, *self.aliases]


class Gazetteer:
    def __init__(self, places: list[Place]):
        self.places = {p.id: p for p in places}
        pairs = []
        for p in places:
            if not p.match:
                continue
            for n in p.names:
                pairs.append((n, p))
        pairs.sort(key=lambda x: -len(x[0]))
        self._pairs = pairs

    @classmethod
    def from_json(cls, rows: list[dict]) -> "Gazetteer":
        return cls([Place(**r) for r in rows])

    def find(self, text: str) -> list[tuple[str, int, int]]:
        """Return (place_id, start, end) for each non-overlapping mention, longest alias first."""
        taken = [False] * len(text)
        hits = []
        for name, place in self._pairs:
            for m in re.finditer(re.escape(name), text):
                s, e = m.span()
                if any(taken[s:e]):
                    continue
                if len(name) == 1:
                    prev = text[s - 1] if s > 0 else ""
                    nxt = text[e] if e < len(text) else ""
                    if prev not in LOCATIVE_PREFIX or (nxt and nxt in place.exclude_next):
                        continue
                for i in range(s, e):
                    taken[i] = True
                hits.append((place.id, s, e))
        hits.sort(key=lambda h: h[1])
        return hits

    def count(self, text: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for pid, _, _ in self.find(text):
            out[pid] = out.get(pid, 0) + 1
        return out
