"""CSS/JSOUP selector parser.

Legado uses a JSOUP-like syntax for CSS selectors:
- Standard CSS: `@css:div.title`
- JSOUP shorthand: `class.bookname@tag.0!0`
  - `class.name` → select by class
  - `tag.name` → select by tag
  - `id.name` → select by id
  - `@tag.N` → get Nth child of tag type
  - `!N` → get Nth attribute or text(0=text, others=attr index)
  - `@text` → get text content
  - `@textNodes` → get text of all child nodes
  - `@href` / `@src` / `@attr` → get attribute
"""

from bs4 import BeautifulSoup, Tag
import re


def parse(rule: str, content: str | Tag) -> str | list[str]:
    if not rule:
        return ""
    if rule.startswith("@css:"):
        return _parse_css(rule[5:], content)
    return _parse_jsoup(rule, content)


def parse_list(rule: str, content: str | Tag) -> list[Tag]:
    if not rule:
        return []
    if rule.startswith("@css:"):
        css_rule = rule[5:]
        selector, _ = _split_attr_selector(css_rule)
        soup = _ensure_soup(content)
        return _select_css(soup, selector)
    return _parse_jsoup_list(rule, content)


def _ensure_soup(content: str | Tag) -> BeautifulSoup | Tag:
    if isinstance(content, Tag):
        return content
    return BeautifulSoup(content, "lxml")


def _parse_css(rule: str, content: str | Tag) -> str | list[str]:
    selector, attr = _split_attr_selector(rule)
    soup = _ensure_soup(content)
    elements = _select_css(soup, selector)
    if not elements:
        return ""
    if attr:
        results = [_get_attr(el, attr) for el in elements]
        return results if len(results) > 1 else results[0]
    results = [el.get_text(strip=True) for el in elements]
    return results if len(results) > 1 else results[0]


def _split_attr_selector(rule: str) -> tuple[str, str]:
    """Split `selector@attr` or `selector` from a CSS rule."""
    if "@" not in rule:
        return rule, ""
    last_at = rule.rfind("@")
    # Check if it's part of a valid CSS selector (e.g. [attr=val])
    before = rule[:last_at]
    if before.count("[") > before.count("]"):
        return rule, ""
    return before, rule[last_at + 1:]


def _get_attr(element: Tag, attr: str) -> str:
    if attr == "text" or attr == "textNodes":
        return element.get_text(strip=True)
    if attr == "href":
        return element.get("href", "")
    if attr == "src":
        return element.get("src", "")
    if attr == "outerHtml":
        return str(element)
    if attr == "innerHTML" or attr == "html":
        return element.decode_contents()
    return element.get(attr, "")


def _select_css(soup: BeautifulSoup | Tag, selector: str) -> list[Tag]:
    selector, index_filter, suffix = _extract_index_filter(selector)
    elements = soup.select(selector)
    if not index_filter:
        return elements

    op, index = index_filter
    if op == "lt":
        elements = elements[:index]
    if op == "gt":
        elements = elements[index + 1:]
    if op == "eq":
        if index < 0:
            index = len(elements) + index
        elements = [elements[index]] if 0 <= index < len(elements) else []
    if suffix:
        nested = []
        for element in elements:
            nested.extend(element.select(suffix))
        return nested
    return elements


def _extract_index_filter(selector: str) -> tuple[str, tuple[str, int] | None, str]:
    match = re.search(r":(lt|gt|eq)\((-?\d+)\)", selector)
    if not match:
        return selector, None, ""
    return selector[: match.start()].strip() or "*", (match.group(1), int(match.group(2))), selector[match.end():].strip()


def _parse_jsoup(rule: str, content: str | Tag) -> str | list[str]:
    """Parse Legado JSOUP shorthand syntax."""
    soup = _ensure_soup(content)

    parts = rule.split("@")
    elements = [soup]
    attr_part = ""

    for i, part in enumerate(parts):
        if not part:
            continue
        if part in ("text", "textNodes", "href", "src", "outerHtml", "innerHTML", "html"):
            attr_part = part
            break
        if part.startswith("attr:"):
            attr_part = part[5:]
            break

        # Selector part
        new_elements = []
        for el in elements:
            selected = _select_jsoup_part(el, part)
            new_elements.extend(selected)
        if not new_elements:
            return ""
        elements = new_elements

    if attr_part:
        results = [_get_attr(el, attr_part) for el in elements if isinstance(el, Tag)]
    else:
        results = [el.get_text(strip=True) for el in elements if isinstance(el, Tag)]

    results = [r for r in results if r]
    if not results:
        return ""
    return results if len(results) > 1 else results[0]


def _parse_jsoup_list(rule: str, content: str | Tag) -> list[Tag]:
    """Parse JSOUP rule and return list of matched elements."""
    soup = _ensure_soup(content)
    parts = rule.split("@")

    elements = [soup]
    for part in parts:
        if not part:
            continue
        if part in ("text", "textNodes", "href", "src", "outerHtml", "innerHTML", "html"):
            break
        if part.startswith("attr:"):
            break
        new_elements = []
        for el in elements:
            selected = _select_jsoup_part(el, part)
            new_elements.extend(selected)
        if not new_elements:
            return []
        elements = new_elements

    return [el for el in elements if isinstance(el, Tag)]


def _select_jsoup_part(element: Tag | BeautifulSoup, part: str) -> list[Tag]:
    """Select elements by a single JSOUP part like 'class.name' or 'tag.div.0'."""
    # Handle index notation: part.N
    index = None
    base = part
    segments = part.split(".")
    if len(segments) >= 2 and segments[-1].lstrip("-").isdigit():
        index = int(segments[-1])
        base = ".".join(segments[:-1])
        segments = base.split(".")

    if not segments:
        return []

    selector_type = segments[0]
    selector_value = ".".join(segments[1:]) if len(segments) > 1 else ""

    if selector_type == "class":
        found = element.find_all(class_=selector_value) if selector_value else []
    elif selector_type == "tag":
        found = element.find_all(selector_value) if selector_value else []
    elif selector_type == "id":
        if index is not None:
            found = element.find_all(id=selector_value)
        else:
            el = element.find(id=selector_value)
            found = [el] if el else []
    elif selector_type == "text":
        found = [el for el in element.find_all(True) if selector_value in (el.get_text() or "")]
    elif selector_type == "children":
        found = [c for c in element.children if isinstance(c, Tag)]
    else:
        if _looks_like_css_selector(part):
            try:
                return element.select(part)
            except Exception:
                return []
        # Try as tag name directly
        found = []
        if isinstance(element, Tag) and element.name == selector_type:
            found.append(element)
        found.extend(element.find_all(selector_type))
        if not found and selector_value:
            # Try as CSS selector
            try:
                found = element.select(part.replace(".", " ."))
            except Exception:
                found = []

    if index is not None and found:
        if index < 0:
            index = len(found) + index
        if 0 <= index < len(found):
            return [found[index]]
        return []

    return found


def _looks_like_css_selector(part: str) -> bool:
    return any(token in part for token in (" ", ">", "+", "~", "[", "#", ":"))
