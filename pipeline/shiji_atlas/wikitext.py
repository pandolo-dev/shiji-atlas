"""Regex cleaning of zh.wikisource wikitext into plain classical Chinese."""
import re

_REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S)
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_VARIANT = re.compile(r"\{\{另\|([^|{}]*)\|([^|{}]*)\}\}")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_LANGCONV_PAIR = re.compile(r"-\{[^{}]*?zh-hant:([^;{}]*);?[^{}]*\}-")
_LANGCONV = re.compile(r"-\{([^{}]*)\}-")
_LINK_LABEL = re.compile(r"\[\[[^\[\]|]*\|([^\[\]]*)\]\]")
_LINK = re.compile(r"\[\[([^\[\]|]*)\]\]")
_BOLD = re.compile(r"'{2,}")
_MAGIC = re.compile(r"__[A-Z]+__+")


def strip_templates(text: str) -> str:
    text = _VARIANT.sub(lambda m: m.group(2), text)
    prev = None
    while prev != text:
        prev = text
        text = _TEMPLATE.sub("", text)
    return text


def clean_inline(text: str) -> str:
    """Clean a single line/paragraph of wikitext markup, keeping the text."""
    text = _COMMENT.sub("", text)
    text = _REF.sub("", text)
    text = strip_templates(text)
    text = _LANGCONV_PAIR.sub(lambda m: m.group(1).strip(), text)
    text = _LANGCONV.sub(lambda m: m.group(1), text)
    text = _LINK_LABEL.sub(lambda m: m.group(1), text)
    text = _LINK.sub(lambda m: m.group(1).split("/")[-1], text)
    text = _TAG.sub("", text)
    text = _BOLD.sub("", text)
    text = _MAGIC.sub("", text)
    text = text.replace("\u3000", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def preprocess(raw: str) -> str:
    """Whole-document pass: drop refs and templates that may span lines."""
    raw = _COMMENT.sub("", raw)
    raw = _REF.sub("", raw)
    raw = re.sub(r"<references\s*/?>", "", raw)
    return strip_templates(raw)
