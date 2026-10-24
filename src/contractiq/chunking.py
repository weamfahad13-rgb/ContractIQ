"""Split a contract into clause-sized chunks.

Chunks keep character offsets into the original text, so a retrieved chunk can be
highlighted in the source panel and compared with CUAD's labeled answer spans.
"""

import re
from dataclasses import dataclass

# A clause heading at the start of a line: "ARTICLE III", "Section 4.2", "9.2 Late delivery",
# "17. FORCE MAJEURE", "(a) The Supplier".
HEADING = re.compile(
    r"^[ \t]*(?:"
    r"(?:article|section|clause)\s+[\dIVXLC]+(?:\.\d+)*"
    r"|\d{1,2}(?:\.\d{1,2}){0,3}\.?[ \t]+(?=[A-Z(\"'؀-ۿ])"
    r"|\([a-z]\)[ \t]+(?=[A-Z])"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

MIN_CHARS = 150  # shorter pieces get merged into the next one
MAX_CHARS = 2000  # longer pieces get split on paragraph breaks
FALLBACK_TARGET = 1200
MIN_HEADINGS = 5  # below this, the contract has no usable structure


@dataclass
class Chunk:
    heading: str
    text: str
    start: int
    end: int


def clean(text: str) -> str:
    """Collapse PDF-extraction whitespace for embedding and display."""
    return re.sub(r"\s+", " ", text).strip()


def _heading_label(raw: str) -> str:
    first = clean(raw.lstrip().split("\n", 1)[0])
    return first[:80] + ("…" if len(first) > 80 else "")


def _paragraph_spans(text: str, start: int, end: int, target: int) -> list[tuple[int, int]]:
    """Pack paragraphs inside text[start:end] into spans of roughly `target` chars."""
    breaks = [m.end() for m in re.finditer(r"\n\s*\n", text[start:end])]
    cuts = [start] + [start + b for b in breaks] + [end]
    spans, s = [], cuts[0]
    for c in cuts[1:]:
        if c - s >= target:
            spans.append((s, c))
            s = c
    if s < end:
        if spans and end - s < MIN_CHARS:
            spans[-1] = (spans[-1][0], end)
        else:
            spans.append((s, end))
    # A single paragraph may still be huge (no blank lines at all): hard-split on sentences.
    out = []
    for s, e in spans:
        while e - s > MAX_CHARS:
            dot = text.rfind(". ", s, s + MAX_CHARS)
            cut = dot + 2 if dot > s + MIN_CHARS else s + MAX_CHARS
            out.append((s, cut))
            s = cut
        out.append((s, e))
    return out


def _split_at(text: str, starts: list[int], s: int, e: int) -> list[tuple[int, int]]:
    """Split text[s:e] at the given heading positions, merging pieces shorter than MIN_CHARS."""
    bounds = [s] + [p for p in starts if s < p < e] + [e]
    merged = []
    for a, b in zip(bounds, bounds[1:]):
        if not text[a:b].strip():
            continue
        if merged and merged[-1][1] - merged[-1][0] < MIN_CHARS:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if len(merged) > 1 and merged[-1][1] - merged[-1][0] < MIN_CHARS:
        tail = merged.pop()
        merged[-1] = (merged[-1][0], tail[1])
    return merged


def chunk_contract(text: str) -> list[Chunk]:
    matches = list(HEADING.finditer(text))
    # Top-level headings ("9. DELIVERY", "ARTICLE III") vs sub-clauses ("9.2", "(a)").
    top = [m.start() for m in matches if not re.search(r"\d\.\d|\([a-z]\)", m.group(), re.I)]
    sub = [m.start() for m in matches]

    if len(sub) < MIN_HEADINGS:
        spans = _paragraph_spans(text, 0, len(text), FALLBACK_TARGET)
    else:
        # Prefer whole top-level clauses; fall back to sub-clauses, then paragraphs, when too long.
        primary = top if len(top) >= MIN_HEADINGS else sub
        spans = []
        for s, e in _split_at(text, primary, 0, len(text)):
            if e - s <= MAX_CHARS:
                spans.append((s, e))
                continue
            for s2, e2 in _split_at(text, sub, s, e):
                spans.extend(_paragraph_spans(text, s2, e2, FALLBACK_TARGET) if e2 - s2 > MAX_CHARS
                             else [(s2, e2)])

    chunks = []
    for s, e in spans:
        body = clean(text[s:e])
        if not body:
            continue
        # Name the chunk after every top-level clause it holds, so a citation never hides one.
        inner = [p for p in top if s < p < e]
        heading = " · ".join(_heading_label(text[p:e]) for p in [s, *inner][:3])
        chunks.append(Chunk(heading=heading, text=body, start=s, end=e))
    return chunks
