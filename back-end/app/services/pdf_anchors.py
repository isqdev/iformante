"""Locate chunk text on its page; coordinates use the rotated page, normalized 0..1."""
from functools import lru_cache
from pathlib import Path
from difflib import SequenceMatcher
import re
import unicodedata
import fitz


def words(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c)))


@lru_cache(maxsize=256)
def locate_chunk(path: str, modified: float, page_number: int, content: str) -> list[dict]:
    with fitz.open(path) as pdf:
        if page_number < 1 or page_number > len(pdf):
            return []
        page = pdf[page_number - 1]
        content = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", content)
        chunk_tokens = words(content)
        page_words = page.get_text("words", sort=True)
        page_tokens, token_words = [], []
        for word in page_words:
            for token in words(word[4]):
                page_tokens.append(token)
                token_words.append(word)
        matcher = SequenceMatcher(a=page_tokens, b=chunk_tokens, autojunk=False)
        lines = {}
        for match in matcher.get_matching_blocks():
            if match.size < min(3, len(chunk_tokens)) or not match.size:
                continue
            for word in token_words[match.a:match.a + match.size]:
                key = (word[5], word[6])
                rect = fitz.Rect(word[:4])
                if key in lines:
                    lines[key] |= rect
                else:
                    lines[key] = rect
        rectangles = []
        for source_rect in lines.values():
            rect = source_rect * page.rotation_matrix
            bounds = page.rect
            rectangles.append({"page": page_number, "x": rect.x0 / bounds.width,
                               "y": rect.y0 / bounds.height, "width": rect.width / bounds.width,
                               "height": rect.height / bounds.height})
        return rectangles or [{"page": page_number}]


def chunk_anchors(path: str | Path | None, page_number: int, content: str):
    if not path or not Path(path).is_file():
        return [{"page": page_number}]
    return locate_chunk(str(path), Path(path).stat().st_mtime, page_number, content)
