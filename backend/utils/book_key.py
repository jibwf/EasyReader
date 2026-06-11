from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_identity_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""

    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()

    if not scheme:
        return value.rstrip("/")

    netloc = parsed.netloc
    path = parsed.path or ""
    query = parsed.query or ""

    if scheme in {"http", "https"}:
        netloc = netloc.lower()
        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        if netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]

        if not path:
            path = "/"
        elif len(path) > 1:
            path = path.rstrip("/")

        if query:
            query_pairs = parse_qsl(query, keep_blank_values=True)
            query_pairs.sort()
            query = urlencode(query_pairs, doseq=True)
    else:
        if len(path) > 1:
            path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, query, ""))


def build_book_key(source_url: str, book_url: str) -> str:
    normalized_source = normalize_identity_url(source_url)
    normalized_book = normalize_identity_url(book_url)
    raw = f"{normalized_source}\n{normalized_book}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"bk_{digest}"
