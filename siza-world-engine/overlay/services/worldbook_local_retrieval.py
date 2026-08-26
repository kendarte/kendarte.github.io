import base64
import gzip
import os
import re
import unicodedata
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path


WORLDBOOK_RETRIEVAL_BUILD = "dm-0.1.4-local-worldbook-v18-retrieval"
WORLDBOOK_VERSION = "1.8"
EXPECTED_PAYLOAD_CHARS = 136904
DEFAULT_MAX_SNIPPETS = 4
DEFAULT_CHAR_BUDGET = 2200
CONTENT_FILES = (
    "wb18-00.txt", "wb18-01.txt", "wb18-02.txt", "wb18-03.txt", "wb18-04.txt",
    "wb18-05a.txt", "wb18-05b.txt", "wb18-05c.txt", "wb18-05d.txt",
    "wb18-06.txt", "wb18-07.txt", "wb18-08.txt", "wb18-09.txt", "wb18-10.txt",
    "wb18-11a.txt", "wb18-11b.txt", "wb18-11c.txt", "wb18-11d.txt", "wb18-11e.txt", "wb18-11f.txt",
)
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


def _candidate_content_dirs(explicit_dir=None):
    seen = set()
    values = []
    if explicit_dir:
        values.append(Path(explicit_dir))
    env_dir = str(os.environ.get("SIZA_WORLDBOOK_CONTENT", "") or "").strip()
    if env_dir:
        values.append(Path(env_dir))

    here = Path(__file__).resolve()
    for parent in here.parents:
        values.append(parent / "rivarica" / "content")

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


def find_worldbook_content_dir(explicit_dir=None):
    for directory in _candidate_content_dirs(explicit_dir=explicit_dir):
        if all((directory / filename).is_file() for filename in CONTENT_FILES):
            return directory
    return None


@lru_cache(maxsize=4)
def _load_visible_text_cached(directory_text):
    directory = Path(directory_text)
    parts = [(directory / filename).read_text(encoding="utf-8").strip() for filename in CONTENT_FILES]
    encoded = "".join(parts)
    if len(encoded) != EXPECTED_PAYLOAD_CHARS:
        raise ValueError(f"INCOMPLETE_WORLDBOOK_V18_PAYLOAD:{len(encoded)}/{EXPECTED_PAYLOAD_CHARS}")
    html_bytes = gzip.decompress(base64.b64decode(encoded, validate=True))
    html_text = html_bytes.decode("utf-8")
    if "Rivarica World Book v1.8" not in html_text:
        raise ValueError("INVALID_WORLDBOOK_V18_CONTENT")
    parser = _VisibleTextParser()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def load_worldbook_visible_text(content_dir=None):
    directory = find_worldbook_content_dir(explicit_dir=content_dir)
    if not directory:
        return {
            "status": "WORLDBOOK_NOT_FOUND",
            "available": False,
            "version": WORLDBOOK_VERSION,
            "text": "",
            "content_dir": None,
            "build": WORLDBOOK_RETRIEVAL_BUILD,
        }
    try:
        text = _load_visible_text_cached(str(directory))
    except Exception as exc:
        return {
            "status": "WORLDBOOK_DECODE_ERROR",
            "available": False,
            "version": WORLDBOOK_VERSION,
            "text": "",
            "content_dir": str(directory),
            "error": str(exc),
            "build": WORLDBOOK_RETRIEVAL_BUILD,
        }
    return {
        "status": "READY",
        "available": True,
        "version": WORLDBOOK_VERSION,
        "text": text,
        "content_dir": str(directory),
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
    phrase_matches = []
    for phrase in query_phrases:
        clean = _fold(phrase)
        if clean and clean in folded:
            score += 250
            phrase_matches.append(clean)
    overlap = sorted(set(query_tokens).intersection(window_tokens))
    score += 35 * len(overlap)
    return score, phrase_matches, overlap


def retrieve_worldbook_context(queries, *, content_dir=None, max_snippets=DEFAULT_MAX_SNIPPETS, char_budget=DEFAULT_CHAR_BUDGET):
    """Retrieve bounded World Book v1.8 excerpts for DM-only context; never grants player Knowledge."""
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

    loaded = load_worldbook_visible_text(content_dir=content_dir)
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
            "version": WORLDBOOK_VERSION,
            "queries": query_phrases,
            "snippets": [],
            "used_chars": 0,
            "content_dir": loaded.get("content_dir"),
            "authority": "DM_CONTEXT_ONLY",
            "player_knowledge": False,
            "build": WORLDBOOK_RETRIEVAL_BUILD,
        }

    query_tokens = sorted({token for phrase in query_phrases for token in _tokens(phrase)})
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
            "source": "RIVARICA_WORLDBOOK_V18_LOCAL",
            "version": WORLDBOOK_VERSION,
            "window_index": row.get("window_index"),
            "score": row.get("score"),
            "matched_terms": row.get("token_matches"),
            "text": text,
        })
        used_chars += len(text)

    return {
        "status": "RETRIEVED" if selected else "NO_MATCH",
        "available": True,
        "version": WORLDBOOK_VERSION,
        "queries": query_phrases,
        "query_tokens": query_tokens,
        "snippets": selected,
        "used_chars": used_chars,
        "content_dir": loaded.get("content_dir"),
        "authority": "DM_CONTEXT_ONLY",
        "player_knowledge": False,
        "build": WORLDBOOK_RETRIEVAL_BUILD,
    }
