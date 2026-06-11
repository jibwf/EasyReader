"""Parse Legado searchUrl / exploreUrl format.

Legado URL formats:
- Simple GET: `https://example.com/search?q={{key}}&page={{page}}`
- POST with body: `https://example.com/search,{"method":"POST","body":"keyword={{key}}"}`
- POST shorthand: `https://example.com/search@keyword={{key}}`
- With charset: `https://example.com/search?q={{key}}|char=gbk`
- JavaScript URL: `<js>...</js>`
"""

import json
import re
import ast
from urllib.parse import quote, urljoin, urlparse


def parse_url(
    url_template: str,
    *,
    keyword: str = "",
    page: int = 1,
    base_url: str = "",
    source_url: str = "",
) -> dict:
    """Parse a Legado URL template into request parameters.

    Returns dict with keys: url, method, headers, body, charset.
    """
    if not url_template:
        return {"url": "", "method": "GET", "headers": {}, "body": None, "charset": None}

    url_template = url_template.strip()

    if url_template.startswith("@js:") or url_template.startswith("<js>"):
        from backend.engine import js_engine

        url_template = js_engine.execute(
            url_template,
            "",
            key=keyword,
            keyword=keyword,
            page=page,
            baseUrl=base_url or source_url,
            sourceUrl=source_url,
        ).strip()
        if not url_template or url_template in {"/", "#"}:
            return {"url": "", "method": "GET", "headers": {}, "body": None, "charset": None}

    # Clean control whitespace that often appears in imported Legado URL templates.
    url_template = re.sub(r"[\t\r\n]+", "", url_template).strip()
    if url_template in {"/", "#"}:
        return {"url": "", "method": "GET", "headers": {}, "body": None, "charset": None}
    if _is_unusable_url(url_template):
        return {"url": "", "method": "GET", "headers": {}, "body": None, "charset": None}

    # Variable substitution
    url_template = _substitute_vars(
        url_template,
        keyword=keyword,
        page=page,
        source_url=source_url or base_url,
    )
    if "{{" in url_template and "}}" in url_template:
        return {"url": "", "method": "GET", "headers": {}, "body": None, "charset": None}

    # Extract charset option
    charset = None
    if "|char=" in url_template:
        url_template, charset = url_template.rsplit("|char=", 1)

    # Extract other pipe options
    headers = {}
    while "|" in url_template:
        before, _, option = url_template.rpartition("|")
        if "=" in option and not option.startswith("http"):
            key, val = option.split("=", 1)
            if key.lower() == "char":
                charset = val
            else:
                headers[key] = val
            url_template = before
        else:
            break

    # Determine method and body
    method = "GET"
    body = None

    # JSON config format: url,{"method":"POST","body":"..."}
    # The URL part may be absolute or relative in imported Legado sources.
    json_config_match = re.match(r"^([^,]+),\s*(\{.+\})\s*$", url_template, re.DOTALL)
    if json_config_match:
        url = json_config_match.group(1).strip()
        if not url.startswith("http"):
            origin = _get_origin(source_url or base_url)
            if origin:
                url = make_absolute_url(url, origin)
        try:
            config = _parse_config_object(json_config_match.group(2))
            method = config.get("method", "POST").upper()
            body = config.get("body", "")
            if "headers" in config:
                headers.update(config["headers"])
            if "charset" in config:
                charset = config["charset"]
        except json.JSONDecodeError:
            url = url_template
        return {"url": url, "method": method, "headers": headers, "body": body, "charset": charset}

    # POST shorthand: url@body
    if "@" in url_template:
        # Make sure it's not part of the URL path
        at_idx = url_template.find("@")
        url_part = url_template[:at_idx]
        if url_part.startswith("http"):
            body_part = url_template[at_idx + 1:]
            return {"url": url_part, "method": "POST", "headers": headers, "body": body_part, "charset": charset}

    # Resolve relative URLs using source_url origin
    final_url = url_template
    if not final_url.startswith("http"):
        origin = _get_origin(source_url or base_url)
        if origin:
            final_url = make_absolute_url(final_url, origin)

    return {"url": final_url, "method": method, "headers": headers, "body": body, "charset": charset}


def _get_origin(url: str) -> str:
    if not url:
        return ""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _is_unusable_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme) and not parsed.netloc


def _parse_config_object(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        normalized = _normalize_js_object(raw)
        try:
            value = ast.literal_eval(normalized)
        except (ValueError, SyntaxError):
            raise json.JSONDecodeError("Invalid URL config object", raw, 0)
    return value if isinstance(value, dict) else {}


def _normalize_js_object(raw: str) -> str:
    """Normalize simple JS object literals used by older Legado sources."""
    normalized = raw.strip()
    normalized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)", r"\1'\2'\3", normalized)
    return normalized


def _substitute_vars(template: str, keyword: str = "", page: int = 1, source_url: str = "") -> str:
    template = template.replace("{{key}}", quote(keyword))
    template = template.replace("{{keyword}}", quote(keyword))
    template = template.replace("{{page}}", str(page))
    # Legado also uses searchKey and searchPage
    template = template.replace("{{searchKey}}", quote(keyword))
    template = template.replace("{{searchPage}}", str(page))
    template = _substitute_source_key(template, source_url)
    # Handle {page - 1} style expressions
    template = re.sub(
        r"\{\{page\s*([+-])\s*(\d+)\}\}",
        lambda m: str(page + int(m.group(2)) * (1 if m.group(1) == "+" else -1)),
        template,
    )
    return template


def _substitute_source_key(template: str, source_url: str) -> str:
    if not source_url:
        return template

    parsed = urlparse(source_url)
    if not parsed.scheme or not parsed.netloc:
        return template

    origin = f"{parsed.scheme}://{parsed.netloc}"
    host = parsed.netloc
    expressions = (
        "source.getKey()",
        "cookie.removeCookie(source.getKey())",
    )

    for expr in expressions:
        token = "{{" + expr + "}}"
        if f"://{token}" in template:
            template = template.replace(token, host)
        else:
            template = template.replace(token, origin)
    return template


def make_absolute_url(url: str, base_url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        # Extract origin from base_url
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    # Relative path
    if base_url:
        return urljoin(base_url, url)
    return url
