"""Download raw wikitext snapshots from zh.wikisource into data/raw."""
import sys
import urllib.parse
import urllib.request

from .build import RAW, SHIJI, TONGJIAN, YANYI

URL = "https://zh.wikisource.org/w/index.php?title={}&action=raw"


def pages() -> list[tuple[str, str]]:
    out = [(f"史記/卷{j:03d}", f"史記_卷{j:03d}.wiki") for j in SHIJI]
    out += [(f"資治通鑑/卷{j:03d}", f"資治通鑑_卷{j:03d}.wiki") for j in TONGJIAN]
    out += [(f"前漢演義/第{n:03d}回", f"前漢演義_第{n:03d}回.wiki") for n in YANYI]
    return out


def main() -> int:
    for title, fname in pages():
        req = urllib.request.Request(URL.format(urllib.parse.quote(title)),
                                     headers={"User-Agent": "shiji-atlas/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            (RAW / fname).write_bytes(r.read())
        print("fetched", title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
