import base64
import gzip
import os
import re
import unicodedata
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path


WORLDBOOK_RETRIEVAL_BUILD = "dm-0.1.1-local-worldbook-v08-retrieval"
DEFAULT_MAX_SNIPPETS = 4
DEFAULT_CHAR_BUDGET = 2200
_CHUNK_RE = re.compile(r'''WB_CHUNKS\s*\.\s*push\s*\(\s*["']([A-Za-z0-9+/=]+)["']\s*\)''')
_TOKEN_RE = re.compile(r"[a-z0-9_:-]+")
_STOPWORDS = {
    "a", "al", "and", "ante", "con", "de", "del", "el", "en", "for", "la", "las", "los",
    "of", "para", "por", "que", "the", "to", "un", "una", "y",
}
_BLOCK_TAGS = {
    "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main", "nav", "p", "section",
    "table", "td", "th", "tr",
}


def _fold(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _tokens(value):
    return [token for token in _TOKEN_RE.findall(_fold(value)) if token not in _STOPWORDS and len(token) > 1]


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        name = str(tag or "").lower()
        if name in {"script", "style", "noscript", "template"}:
            self.hidden_depth += 1
            return
        if self.hidden_depth == 0 and name in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        name = str(tag or "").lower()
        if name in {"script", "style", "noscript", "template"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
            return
        if self.hidden_depth == 0 and name in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden_depth == 0 and str(data or "").strip():
            self.parts.append(str(data))

    def text(self):
        raw = "".join(self.parts).replace("\r", "\n")
        lines = []
        for line in raw.split("\n"):
            clean = re.sub(r"\s+", " ", line).strip()
            if clean:
                lines.append(clean)
        return "\n".join(lines)


def _candidate_chunk_dirs(explicit_dir=None):
    seen = set()
    values = []
    if explicit_dir:
        values.append(Path(explicit_dir))
    env_dir = str(os.environ.get("SIZA_WORLDBOOK_CHUNKS", "") or "").strip()
    if env_dir:
        values.append(Path(env_dir))

    here = Path(__file__).resolve()
    for parent in here.parents:
        values.append(parent / "rivarica" / "chunks")

    for value in values:
        try:
            resolved = value.expanduser().resolve()
        except Exception:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        yield resolved


def find_worldbook_chunks_dir(explicit_dir=None):
    for directory in _candidate_chunk_dirs(explicit_dir=explicit_dir):
        if all((directory / f"wb-{index:02d}.js").is_file() for index in range(6)):
            return directory
    return None


def _extract_chunk_payload(path):
    source = Path(path).read_text(encoding="utf-8")
    matches = _CHUNK_RE.findall(source)
    if not matches:
        raise ValueError(f"INVALID_WORLDBOOK_CHUNK:{Path(path).name}")
    return "".join(matches)


@lru_cache(maxsize=4)
def _load_visible_text_cached(directory_text):
    directory = Path(directory_text)
    encoded = "".join(_extract_chunk_payload(directory / f"wb-{index:02d}.js") for index in range(6))
    html_bytes = gzip.decompress(base64.b64decode(encoded, validate=True))
    html_text = html_bytes.decode("utf-8")
    parser = _VisibleTextParser()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def load_worldbook_visible_text(chunks_dir=None):
    directory = find_worldbook_chunks_dir(explicit_dir=chunks_dir)
    if not directory:
        return {
            "status": "WORLDBOOK_NOT_FOUND",
            "available": False,
            "text": "",
            "chunks_dir": None,
            "build": WORLDBOOK_RETRIEVAL_BUILD,
        }
    try:
        text = _load_visible_text_cached(str(directory))
    except Exception as exc:
        return {
            "status": "WORLDBOOK_DECODE_ERROR",
            "available": False,
            "text": "",
            "chunks_dir": str(directory),
            "error": str(exc),
            "build": WORLDBOOK_RETRIEVAL_BUILD,
        }
    return {
        "status": "READY",
        "available": True,
        "text": text,
        "chunks_dir": str(directory),
        "build": WORLDBOOK_RETRIEVAL_BUILD,
    }


def _windows(text, target_chars=900, overlap_lines=2):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    output = []
    start = 0
    while start < len(lines):
        used = 0
        end = start
        while end < len(lines):
            addition = len(lines[end]) + (1 if end > start else 0)
            if end > start and used + addition > target_chars:
                break
            used += addition
            end += 1
        if end <= start:
            end = start + 1
        output.append({"start_line": start, "end_line": end - 1, "text": "\n".join(lines[start:end])})
        if end >= len(lines):
            break
        start = max(start + 1, end - max(0, int(overlap_lines)))
    return output


def _score_window(window_text, query_phrases, query_tokens):
    folded = _fold(window_text)
    window_tokens = set(_tokens(window_text))
    score = 0
    matched = []
    for phrase in query_phrases:
        clean = _fold(phrase)
        if clean and clean in folded:
            score += 250
            matched.append(clean)
    overlap = sorted(set(query_tokens).intersection(window_tokens))
    score += 35 * len(overlap)
    return score, matched, overlap


def retrieve_worldbook_context(queries, *, chunks_dir=None, max_snippets=DEFAULT_MAX_SNIPPETS, char_budget=DEFAULT_CHAR_BUDGET):
    """Retrieve bounded local World Book excerpts for DM-only adjudication context."""
    query_phrases = []
    for value in list(queries or []):
        clean = str(value or "").strip()
        if clean and clean not in query_phrases:
            query_phrases.append(clean)

    try:
        max_snippets = max(0, int(max_snippets))
    except (TypeError, ValueError):
        max_snippets = DEFAULT_MAX_SNIPPETS
    try:
        char_budget = max(0, int(char_budget))
    except (TypeError, ValueError):
        char_budget = DEFAULT_CHAR_BUDGET

    loaded = load_worldbook_visible_text(chunks_dir=chunks_dir)
    if not loaded.get("available"):
        return {
            **loaded,
            "queries": query_phrases,
            "snippets": [],
            "used_chars": 0,
            "authority": "DM_CONTEXT_ONLY",
            "player_knowledge": False,
        }
    if not query_phrases or max_snippets <= 0 or char_budget <= 0:
        return {
            "status": "NO_QUERY",
            "available": True,
            "queries": query_phrases,
            "snippets": [],
            "used_chars": 0,
            "chunks_dir": loaded.get("chunks_dir"),
            "authority": "DM_CONTEXT_ONLY",
            "player_knowledge": False,
            "build": WORLDBOOK_RETRIEVAL_BUILD,
        }

    query_tokens = []
    for phrase in query_phrases:
        query_tokens.extend(_tokens(phrase))
    query_tokens = sorted(set(query_tokens))

    ranked = []
    for index, window in enumerate(_windows(loaded.get("text") or "")):
        score, phrase_matches, token_matches = _score_window(window.get("text"), query_phrases, query_tokens)
        if score <= 0:
            continue
        ranked.append({
            "window_index": index,
            "score": score,
            "phrase_matches": phrase_matches,
            "token_matches": token_matches,
            "text": window.get("text"),
        })
    ranked.sort(key=lambda row: (-int(row.get("score") or 0), int(row.get("window_index") or 0)))

    selected = []
    used_chars = 0
    seen_text = set()
    for row in ranked:
        if len(selected) >= max_snippets:
            break
        text = str(row.get("text") or "").strip()
        key = _fold(text)
        if not text or key in seen_text:
            continue
        remaining = char_budget - used_chars
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining].rsplit(" ", 1)[0].strip()
        if not text:
            break
        seen_text.add(key)
        selected.append({
            "source": "RIVARICA_WORLDBOOK_V08_LOCAL",
            "window_index": row.get("window_index"),
            "score": row.get("score"),
            "matched_terms": row.get("token_matches"),
            "text": text,
        })
        used_chars += len(text)

    return {
        "status": "RETRIEVED" if selected else "NO_MATCH",
        "available": True,
        "queries": query_phrases,
        "query_tokens": query_tokens,
        "snippets": selected,
        "used_chars": used_chars,
        "chunks_dir": loaded.get("chunks_dir"),
        "authority": "DM_CONTEXT_ONLY",
        "player_knowledge": False,
        "build": WORLDBOOK_RETRIEVAL_BUILD,
    }
