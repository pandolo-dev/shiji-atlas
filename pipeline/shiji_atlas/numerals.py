"""Chinese numeral helpers for reign years, BCE labels and months."""
import re

DIGITS = {"〇": 0, "○": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "元": 1, "正": 1}


def cn_to_int(s: str) -> int:
    """Parse 二十三 / 十二 / 二〇八 (positional) / 元 into an int."""
    s = s.strip()
    if not s:
        raise ValueError("empty numeral")
    if "十" not in s and "百" not in s:
        val = 0
        for ch in s:
            val = val * 10 + DIGITS[ch]
        return val
    total, cur = 0, 0
    for ch in s:
        if ch == "百":
            total += (cur or 1) * 100
            cur = 0
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        else:
            cur = DIGITS[ch]
    return total + cur


# Qin / early Han used the Zhuanxu calendar: the civil year opens in month 10.
MONTH_ORDER = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
SEASON_FIRST_MONTH = {"冬": 10, "春": 1, "夏": 4, "秋": 7}

MONTH_RE = re.compile(r"(閏)?(正|十二|十一|十|[一二三四五六七八九])月")


def month_index(month: int) -> int:
    """Position of a month inside the Zhuanxu civil year (十月 = 0)."""
    return MONTH_ORDER.index(month)


def sort_key(year_bce: int, month: int | None) -> float:
    """Monotonic key: later events get larger keys. year_bce is positive (209 = 209 BCE)."""
    idx = month_index(month) if month else 0
    return -year_bce + idx / 12.0


def find_months(text: str) -> list[int]:
    out = []
    for m in MONTH_RE.finditer(text):
        out.append(cn_to_int(m.group(2)))
    return out
