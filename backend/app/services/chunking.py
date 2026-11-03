"""Split plain-text guide articles (MediaWiki 'explaintext' style) into retrievable chunks."""
import re

HEAD = re.compile(r"^=+\s*(.+?)\s*=+$")
SKIP = {"references", "external links", "see also", "notes", "sources"}


def split_sections(text: str) -> list[tuple[str, str]]:
    sections, title, buf = [], "Overview", []
    for line in text.splitlines():
        m = HEAD.match(line.strip())
        if m:
            if buf:
                sections.append((title, "\n".join(buf).strip()))
            title, buf = m.group(1), []
        else:
            buf.append(line)
    if buf:
        sections.append((title, "\n".join(buf).strip()))
    return [(t, b) for t, b in sections if b and t.lower() not in SKIP]


def chunk_text(text: str, max_chars: int = 900, min_chars: int = 80) -> list[tuple[str, str]]:
    chunks = []
    for title, body in split_sections(text):
        cur = ""
        units = []
        for para in [p.strip() for p in re.split(r"\n\s*\n|\n", body) if p.strip()]:
            # very long paragraphs are split on sentence boundaries so no chunk balloons
            units += re.split(r"(?<=[.!?])\s+", para) if len(para) > max_chars else [para]
        for para in units:
            if cur and len(cur) + len(para) + 1 > max_chars:
                chunks.append((title, cur))
                cur = ""
            cur = (cur + " " + para).strip()
        if cur:
            chunks.append((title, cur))
    return [(t, c) for t, c in chunks if len(c) >= min_chars]
